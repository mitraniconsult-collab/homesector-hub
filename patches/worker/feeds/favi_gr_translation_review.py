"""Export a read-only, source-digest-backed review queue for Greek product copy.

Run manually on the durable feed worker. No Shopify mutations are made. The CSV
contains source content, current Greek translations and their Shopify digests;
an approved translation must be checked against fresh digests before any later
translationsRegister operation. Variant color translations are a separate queue.
"""
import argparse
import csv
import json
import os
from pathlib import Path


QUERY = """
query ReviewGreekProductCopy($id: ID!) {
  translatableResource(resourceId: $id) {
    resourceId
    translatableContent { key value digest locale }
    translations(locale: "el") { key value outdated }
  }
}
"""
FIELDS = (
    "product_id", "handle", "favi_category", "source_title", "source_body_html",
    "title_digest", "body_html_digest", "greek_title", "greek_body_html",
    "title_needs_review", "body_html_needs_review", "reviewed_greek_title",
    "reviewed_greek_body_html", "review_status",
)


def review_row(product, category, resource):
    if not resource or resource.get("resourceId") != product["id"]:
        raise RuntimeError("Incomplete Shopify translatable resource")
    content = {x["key"]: x for x in resource.get("translatableContent") or []
               if x.get("key") in ("title", "body_html")}
    translations = {x["key"]: x for x in resource.get("translations") or []
                    if x.get("key") in ("title", "body_html")}
    if not all(content.get(k, {}).get("digest") for k in ("title", "body_html")):
        raise RuntimeError("Missing Shopify source content digest")
    needs = {
        key: not str(translations.get(key, {}).get("value") or "").strip()
        or bool(translations.get(key, {}).get("outdated"))
        for key in ("title", "body_html")
    }
    if not any(needs.values()):
        return None
    return {
        "product_id": product["id"], "handle": product.get("handle") or "",
        "favi_category": category["path"],
        "source_title": content["title"].get("value") or "",
        "source_body_html": content["body_html"].get("value") or "",
        "title_digest": content["title"]["digest"],
        "body_html_digest": content["body_html"]["digest"],
        "greek_title": translations.get("title", {}).get("value") or "",
        "greek_body_html": translations.get("body_html", {}).get("value") or "",
        "title_needs_review": needs["title"], "body_html_needs_review": needs["body_html"],
        "reviewed_greek_title": "", "reviewed_greek_body_html": "",
        "review_status": "PENDING",
    }


def export(source_folder, output, limit=50, taxonomy_id=None, store=None, token=None):
    from .durable_journal import DurableJournal
    from .favi_gr_taxonomy import categories_for_products
    from .shopify_auth import get_admin_token
    from .shopify_translations import _post_with_throttle
    if not 1 <= limit <= 500:
        raise ValueError("limit must be 1..500")
    source_folder, output = Path(source_folder).resolve(), Path(output).resolve()
    if output == source_folder / "records.jsonl" or output == source_folder / "manifest.json":
        raise ValueError("Refusing to overwrite source journal")
    meta, products = DurableJournal(source_folder).load()
    if not meta["finished"] or len(products) != meta["products"]:
        raise RuntimeError("Greek source snapshot is incomplete")
    greek = [p for p in products if p.get("status") == "ACTIVE"
             and p.get("published_GR") is True
             and (not taxonomy_id or (p.get("category") or {}).get("id") == taxonomy_id)]
    mapped = categories_for_products(greek, {})
    candidates = sorted((p for p in greek if p["id"] in mapped),
                        key=lambda p: p["id"])
    store = (store or os.getenv("SHOPIFY_STORE", "")).strip()
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify hostname")
    token = token or get_admin_token(store)
    url = f"https://{store}/admin/api/2026-07/graphql.json"
    rows, checked = [], 0
    for product in candidates:
        data = _post_with_throttle(url, token, QUERY, {"id": product["id"]})
        row = review_row(product, mapped[product["id"]], data.get("translatableResource"))
        checked += 1
        if row:
            rows.append(row)
        if len(rows) >= limit:
            break
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, output)
    return {"source_products": len(products), "eligible_mapped_products": len(candidates),
            "shopify_resources_checked": checked, "review_rows": len(rows),
            "csv": str(output), "shopify_mutations": 0}


def main():
    parser = argparse.ArgumentParser(description="Export Greek FAVI copy review CSV")
    parser.add_argument("--source-folder", required=True, help="Completed GR durable journal folder")
    parser.add_argument("--output", required=True, help="Private CSV path on durable storage")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--taxonomy-id", help="Optional exact Shopify taxonomy GID")
    args = parser.parse_args()
    print(json.dumps(export(args.source_folder, args.output, args.limit, args.taxonomy_id),
                     sort_keys=True))


if __name__ == "__main__":
    main()
