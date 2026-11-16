"""Refresh Shopify variant costs from the current Easyrea purchase prices."""
from collections import Counter, defaultdict
import csv
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import os
from pathlib import Path

import runtime
from import_products import Shopify, easyrea_login, fetch_catalog
from import_rules import VENDORS, ean, sku


SCAN = """query CostVariants($after:String) {
  shop { currencyCode }
  productVariants(first:50,after:$after) {
    nodes { id sku barcode product { id status vendor }
      inventoryItem { unitCost { amount currencyCode } } }
    pageInfo { hasNextPage endCursor }
  }
}"""
WRITE = """mutation UpdateCost($productId:ID!,$variants:[ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId:$productId,variants:$variants) {
    productVariants { id inventoryItem { unitCost { amount currencyCode } } }
    userErrors { field message }
  }
}"""


def supplier_cost(value):
    try:
        cents = Decimal(str(value))
        if cents.is_finite() and cents > 0 and cents == cents.to_integral_value():
            cost = cents / 100
            return cost, cost.to_integral_value(rounding=ROUND_CEILING)
    except (InvalidOperation, TypeError, ValueError):
        pass
    return None, None


def variants(shop):
    cursor = None
    seen = set()
    while True:
        data = shop.call(SCAN, {"after": cursor})
        if data["shop"]["currencyCode"] != "EUR":
            raise RuntimeError("Задачата изисква валута EUR в Shopify.")
        result = data["productVariants"]
        yield from result["nodes"]
        info = result["pageInfo"]
        if not info["hasNextPage"]:
            return
        cursor = info["endCursor"]
        if not cursor or cursor in seen or not result["nodes"]:
            raise RuntimeError("Непълна Shopify пагинация.")
        seen.add(cursor)


def assess(variant, catalog, conflicts, sku_counts):
    code = sku(variant.get("sku"))
    source = catalog.get(code)
    remote = variant["inventoryItem"]["unitCost"]
    current = Decimal(remote["amount"]) if remote else None
    if variant["product"]["status"] == "ARCHIVED":
        return current, None, None, "ARCHIVED"
    if not source:
        return current, None, None, "NO_EASYREA_MATCH"
    if code in conflicts or sku_counts[code] != 1:
        return current, None, None, "SKU_CONFLICT"
    vendor = VENDORS.get(str(source.get("marque") or "").strip().upper())
    barcode = ean(variant.get("barcode"))
    supplier_barcode = ean(source.get("gencode"))
    if (not vendor or vendor.casefold() != variant["product"]["vendor"].strip().casefold()
            or (barcode and supplier_barcode and barcode != supplier_barcode)):
        return current, None, None, "IDENTITY_MISMATCH"
    if remote and remote["currencyCode"] != "EUR":
        return current, None, None, "CURRENCY_MISMATCH"
    cost, rounded = supplier_cost(source.get("prixAchat"))
    if rounded is None:
        return current, None, None, "INVALID_SUPPLIER_PRICE"
    return current, cost, rounded, "UNCHANGED" if current == rounded else "UPDATE"


def main():
    dry = runtime.dry_run(default=True)
    config = runtime.require_env(
        "EASYREA_LOGIN", "EASYREA_PASSWORD", "SHOPIFY_STORE",
        "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET",
    )
    shop = Shopify(config)
    session, xsrf = easyrea_login()
    catalog, conflicts, _ = fetch_catalog(session, xsrf, compare_purchase_prices=True)
    session.close()
    all_variants = list(variants(shop))
    sku_counts = Counter(sku(v.get("sku")) for v in all_variants)
    pending = defaultdict(list)
    counts = Counter()
    report = Path(os.environ.get("HUB_REPORT_DIR", ".")) / "shopify_cost_refresh.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.writer(fp)
        writer.writerow(["variant_id", "sku", "current_eur", "easyrea_eur", "rounded_eur", "status"])

        def record(row, status):
            writer.writerow([*row, status])
            counts[status] += 1

        for v in all_variants:
            current, cost, rounded, status = assess(v, catalog, conflicts, sku_counts)
            row = (v["id"], sku(v.get("sku")), current, cost, rounded)
            if status == "UPDATE" and not dry:
                pending[v["product"]["id"]].append(row)
            else:
                record(row, "WOULD_UPDATE" if status == "UPDATE" else status)
        fp.flush()
        batches = [(product_id, rows[start:start + 100])
                   for product_id, rows in pending.items()
                   for start in range(0, len(rows), 100)]
        for number, (product_id, rows) in enumerate(batches, 1):
            inputs = [{"id": row[0], "inventoryItem": {"cost": str(row[4])}} for row in rows]
            try:
                result = Shopify.checked(
                    shop.call(WRITE, {"productId": product_id, "variants": inputs}),
                    "productVariantsBulkUpdate",
                )
                actual = {v["id"]: v["inventoryItem"]["unitCost"] for v in result["productVariants"]}
                for row in rows:
                    value = actual.get(row[0])
                    verified = value and value["currencyCode"] == "EUR" and Decimal(value["amount"]) == row[4]
                    record(row, "UPDATED" if verified else "UNVERIFIED")
            except Exception as exc:
                for row in rows:
                    record(row, "WRITE_ERROR")
                print(f"[cost] {product_id}: {exc}", flush=True)
            fp.flush()
            if number % 25 == 0:
                print(f"[cost] {number}/{len(batches)} партиди", flush=True)
    print(f"[cost] {'TEST' if dry else 'REAL'} {dict(counts)}", flush=True)
    return int(bool(counts["WRITE_ERROR"] or counts["UNVERIFIED"]))


if __name__ == "__main__":
    raise SystemExit(main())
