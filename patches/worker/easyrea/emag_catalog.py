#!/usr/bin/env python3
"""Read-only, complete Shopify variant audit for a future eMAG feed.

No marketplace requests are made. The CSV is a staging artifact, not an
eMAG import file: category characteristics and offer matching require mapping.
"""
import csv
import datetime as dt
import json
import os
from pathlib import Path
import time

import runtime

VERSION = "2026-04"
QUERY = """query EmagCandidates($cursor:String) {
  productVariants(first:100,after:$cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id sku barcode title price inventoryQuantity
      image { url }
      product { id title vendor handle status descriptionHtml
        productType category { name }
        featuredImage { url }
      }
    }
  }
}"""
COLUMNS = ["shopify_product_id", "shopify_variant_id", "sku", "ean", "vendor",
           "product_title", "variant_title", "product_type", "shopify_category",
           "price_shopify", "inventory_shopify", "image_url", "product_url",
           "eligibility", "issues"]


def valid_ean(raw):
    value = (raw or "").strip()
    if len(value) not in (8, 13) or not value.isascii() or not value.isdigit():
        return False
    digits = [int(char) for char in value]
    total = sum(d * (3 if offset % 2 == 0 else 1)
                for offset, d in enumerate(reversed(digits[:-1])))
    return (10 - total % 10) % 10 == digits[-1]


def convert(variant, store):
    product = variant["product"]
    sku = (variant.get("sku") or "").strip()
    ean = (variant.get("barcode") or "").strip()
    product_id = product["id"].rsplit("/", 1)[-1]
    variant_id = variant["id"].rsplit("/", 1)[-1]
    image = variant.get("image") or product.get("featuredImage") or {}
    issues = []
    if product.get("status") != "ACTIVE":
        issues.append("not_active")
    if not sku:
        issues.append("missing_sku")
    if not ean:
        issues.append("missing_ean")
    elif not valid_ean(ean):
        issues.append("invalid_ean")
    if not image.get("url"):
        issues.append("missing_image")
    if not product.get("descriptionHtml"):
        issues.append("missing_description")
    if not product.get("category"):
        issues.append("missing_shopify_category")
    if not (variant.get("price") or ""):
        issues.append("missing_price")
    return dict(shopify_product_id=product_id, shopify_variant_id=variant_id,
                sku=sku, ean=ean, vendor=product.get("vendor") or "",
                product_title=product.get("title") or "",
                variant_title=variant.get("title") or "",
                product_type=product.get("productType") or "",
                shopify_category=(product.get("category") or {}).get("name") or "",
                price_shopify=variant.get("price") or "",
                inventory_shopify=variant.get("inventoryQuantity"),
                image_url=image.get("url") or "",
                product_url=f"https://{store}/products/{product.get('handle', '')}?variant={variant_id}",
                eligibility="review" if issues else "mapping_required",
                issues=";".join(issues))


def fetch_page(store, token, cursor):
    import requests
    for attempt in range(6):
        try:
            response = requests.post(
                f"https://{store}/admin/api/{VERSION}/graphql.json",
                headers={"X-Shopify-Access-Token": token},
                json={"query": QUERY, "variables": {"cursor": cursor}}, timeout=60)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.RequestException("transient Shopify error")
            response.raise_for_status()
            body = response.json()
            if body.get("errors"):
                if all(e.get("extensions", {}).get("code") == "THROTTLED" for e in body["errors"]):
                    raise requests.RequestException("throttled")
                raise RuntimeError("Shopify GraphQL returned validation errors")
            connection = (body.get("data") or {}).get("productVariants")
            if not connection or not connection.get("pageInfo") or "nodes" not in connection:
                raise RuntimeError("Incomplete Shopify response")
            return connection
        except requests.RequestException:
            if attempt == 5:
                raise RuntimeError("Shopify unavailable after six attempts") from None
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError("Shopify pagination failed")


def collect(store, token):
    rows, seen, cursor = [], set(), None
    while True:
        page = fetch_page(store, token, cursor)
        for item in page["nodes"]:
            if item["id"] in seen:
                raise RuntimeError("Duplicate variant returned by Shopify pagination")
            seen.add(item["id"])
            rows.append(convert(item, store))
        print(f"[eMAG] Shopify variants scanned: {len(rows)}", flush=True)
        info = page["pageInfo"]
        if not info["hasNextPage"]:
            break
        next_cursor = info.get("endCursor")
        if not next_cursor or next_cursor == cursor or not page["nodes"]:
            raise RuntimeError("Incomplete Shopify pagination")
        cursor = next_cursor

    # Duplicate EAN and SKU are unsafe for matching existing marketplace offers.
    for field in ("sku", "ean"):
        counts = {}
        for row in rows:
            if row[field]:
                counts[row[field]] = counts.get(row[field], 0) + 1
        for row in rows:
            if row[field] and counts[row[field]] > 1:
                flag = "duplicate_" + field
                row["issues"] = ";".join(filter(None, (row["issues"], flag)))
                row["eligibility"] = "review"
    return rows


def main():
    import requests
    creds = runtime.require_env("SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET")
    response = requests.post(f"https://{creds['SHOPIFY_STORE']}/admin/oauth/access_token",
                             json={"grant_type": "client_credentials",
                                   "client_id": creds["SHOPIFY_CLIENT_ID"],
                                   "client_secret": creds["SHOPIFY_CLIENT_SECRET"]}, timeout=30)
    response.raise_for_status()
    token = response.json()["access_token"]
    rows = collect(creds["SHOPIFY_STORE"], token)
    dest = Path(os.environ.get("HUB_REPORT_DIR", "."))
    dest.mkdir(parents=True, exist_ok=True)
    with (dest / "emag_shopify_catalog.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    summary = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "mode": "read_only_staging", "variants": len(rows),
               "active_variants": sum("not_active" not in r["issues"] for r in rows),
               "requires_review": sum(r["eligibility"] == "review" for r in rows),
               "ready_for_category_mapping": sum(r["eligibility"] == "mapping_required" for r in rows),
               "not_submitted_to_emag": True}
    (dest / "emag_catalog_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
