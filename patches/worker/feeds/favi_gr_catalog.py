"""Restartable private FAVI Greece catalog scan and quality report.

Run on the confirmed durable feed mount. This never publishes a destination URL.
The operator-supplied JSON files contain checked product GIDs for Greek landing
pages and per-product Greek categories; absent files are treated as empty gates.
"""
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

from .batch_job import post_graphql
from .durable_journal import DurableJournal
from .favi_gr_preview import create_preview
from .favi_gr_delivery import publish_preview
from .favi_gr_taxonomy import categories_for_products
from .favi_gr_collection_urls import verify_collection_urls
from .favi_gr_urls import verify_market_urls
from .markets_catalog import catalog_query, read_remaining_variants
from .shopify_auth import get_admin_token
from .shopify_translations import fetch_translations
from .xml_audit import validate_xml
from .favi_gr_audit import audit_favi_gr


def _inputs(root):
    root = Path(root)
    categories_path = root / "favi-gr-verified-categories.json"
    urls_path = root / "favi-gr-verified-url-ids.json"
    categories = json.loads(categories_path.read_text(encoding="utf-8")) if categories_path.exists() else {}
    urls = json.loads(urls_path.read_text(encoding="utf-8")) if urls_path.exists() else []
    if not isinstance(categories, dict) or not isinstance(urls, list):
        raise ValueError("Invalid Greek verification files")
    return categories, urls


def execute(batch_limit=10, root=None, store=None, token=None, should_stop=lambda: False,
            source_folder=None, publish=None, deadline=None):
    if not isinstance(batch_limit, int) or not 1 <= batch_limit <= 1000:
        raise ValueError("batch_limit must be 1..1000")
    root = root or os.environ.get("FEED_DURABLE_PATH")
    if not root:
        raise ValueError("Durable mount path is not configured")
    journal = DurableJournal(source_folder or Path(root) / "favi-gr-source")
    meta, _ = journal.load()
    if meta["finished"]:
        return finalize(journal, root, store=store, token=token, publish=publish,
                        deadline=deadline, should_stop=should_stop)
    store = store or os.environ.get("SHOPIFY_STORE", "")
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify hostname")
    token = token or get_admin_token(store)
    url = f"https://{store}/admin/api/2026-07/graphql.json"
    cursor = meta["cursor"]
    seen = set()
    for _ in range(batch_limit):
        if should_stop():
            break
        if cursor is not None and cursor in seen:
            raise RuntimeError("Repeated Shopify pagination cursor")
        seen.add(cursor)
        page = post_graphql(url, token, catalog_query(gr_only=True), {"cursor": cursor})["products"]
        nodes = page["nodes"]
        for product in nodes:
            variants = product["variants"]
            if variants["pageInfo"]["hasNextPage"]:
                variants["nodes"].extend(read_remaining_variants(
                    url, token, product["id"], variants["pageInfo"]["endCursor"], gr_only=True))
                variants["pageInfo"]["hasNextPage"] = False
        end = page["pageInfo"]["endCursor"]
        more = bool(page["pageInfo"]["hasNextPage"])
        if (more and (not nodes or not end or end == cursor)) or (not more and not nodes):
            raise RuntimeError("Invalid Shopify catalog page")
        meta = journal.append_page(end, nodes, meta["products"] + len(nodes),
                                   finished=not more)
        cursor = end
        print(f"[favi-gr-scan] checkpoint products={meta['products']}", flush=True)
        if not more:
            return finalize(journal, root, store=store, token=token, publish=publish,
                            deadline=deadline, should_stop=should_stop)
    return {"status": "incomplete", "source_products": meta["products"],
            "cursor_saved": True, "published": False}


def finalize(journal, root, store=None, token=None, publish=None,
             deadline=None, should_stop=lambda: False):
    meta, products = journal.load()
    if not meta["finished"] or len(products) != meta["products"]:
        raise RuntimeError("Incomplete Greek source catalog")
    categories, urls = _inputs(root)
    greek_products = [p for p in products if p.get("published_GR") is True
                      and p.get("status") == "ACTIVE"]
    categories = categories_for_products(greek_products, categories)
    translated_variant_map = None
    if deadline is not None:
        from .favi_gr_finalize import collect
        collected = collect(journal, greek_products, categories, set(urls), store, token,
                            deadline, should_stop)
        if collected["status"] == "yielded":
            return {"status": "yielded", "stage": collected["stage"],
                    "source_products": meta["products"], "published": False}
        translated_map = collected["translated_map"]
        auto_urls = collected["auto_urls"]
        collection_urls = collected["collection_urls"]
        url_check = collected["url_check"]
        collection_check = collected["collection_check"]
        translated_variant_map = collected["translated_variant_map"]
    else:
        translated_map = fetch_translations(
            [p["id"] for p in greek_products if p["id"] in categories],
            store=store, token=token, market="GR")
        auto_urls, url_check = verify_market_urls(
            greek_products, categories, translated_map=translated_map)
        print("[favi-gr-url] " + json.dumps(url_check, sort_keys=True), flush=True)
        missing = [p for p in greek_products if p["id"] in categories and p["id"] not in auto_urls]
        if missing:
            shop = store or os.getenv("SHOPIFY_STORE", "")
            if not shop.endswith(".myshopify.com") or "/" in shop:
                raise ValueError("Invalid Shopify hostname for GR collection paths")
            collection_urls, collection_check = verify_collection_urls(
                missing, set(), shop, token or get_admin_token(shop))
        else:
            collection_urls, collection_check = {}, {"checked": 0, "verified": 0}
    for product in greek_products:
        if product["id"] in auto_urls:
            product["verified_market_url_GR"] = auto_urls[product["id"]]
        if product["id"] in collection_urls:
            product["verified_market_url_GR"] = collection_urls[product["id"]]
    print("[favi-gr-collection-url] " + json.dumps(collection_check, sort_keys=True), flush=True)
    if deadline is not None and (should_stop() or time.time() >= deadline):
        return {"status": "yielded", "stage": "serialize",
                "source_products": meta["products"], "published": False}
    xml, report = create_preview(
        greek_products, categories, set(urls) | set(auto_urls) | set(collection_urls),
        translated_map=translated_map, translated_variant_map=translated_variant_map)
    report["verified_collection_url_check"] = collection_check
    report["reviewed_category_products"] = len(categories)
    report["verified_url_check"] = url_check
    report["source_products"] = meta["products"]
    report["greek_published_products"] = len(greek_products)
    report["greek_published_variants"] = sum(
        len((p.get("variants") or {}).get("nodes") or []) for p in greek_products)
    report["mapped_category_products"] = len(categories)
    report["verified_market_url_products"] = len(
        (set(urls) | set(auto_urls) | set(collection_urls)) & set(categories))
    report["localized_copy_products_in_mapped_categories"] = sum(
        {"title", "body_html"}.issubset({
            entry.get("key") for entry in
            translated_map.get(pid, {}).get("GR", []) if entry.get("value")
        }) for pid in categories)
    report["top_source_product_types"] = Counter(
        str(p.get("productType") or "").strip() for p in greek_products
    ).most_common(50)
    report["taxonomy_observed_products"] = sum(bool(p.get("category")) for p in greek_products)
    report["top_shopify_taxonomy"] = Counter(
        ((p.get("category") or {}).get("id"), (p.get("category") or {}).get("fullName"))
        for p in greek_products if p.get("category")
    ).most_common(50)
    report["source_complete"] = True
    # The journal manifest is committed only after its last Shopify page.
    # Re-finalizing an old journal must not disguise the age of its source.
    report["source_snapshot_at"] = datetime.fromtimestamp(
        journal.manifest.stat().st_mtime, timezone.utc).isoformat()
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["sha256"] = hashlib.sha256(xml).hexdigest()
    audit = validate_xml(xml, "GR", max_issues=0)
    favi_audit = audit_favi_gr(xml)
    report["xml_preflight_audit"] = audit
    report["favi_gr_preflight_audit"] = favi_audit
    report["private_audit_passed"] = bool(audit["passed"] and favi_audit["passed"])
    if audit["items"] != report["xml_items"] or audit["unique_ids"] != audit["items"]:
        raise RuntimeError("Greek preview audit failed")
    folder = journal.root
    # Only private files on the mounted volume. A later publisher must require
    # category, language, variant and destination acceptance checks.
    for name, data in (("favi-gr-private.xml", xml),
                       ("favi-gr-report.json", json.dumps(report, ensure_ascii=False, indent=2).encode())):
        temporary = folder / (name + ".tmp")
        with temporary.open("wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, folder / name)
    print("[favi-gr-scan] " + json.dumps(report, sort_keys=True), flush=True)
    if publish is None:
        publish = os.getenv("FEED_FAVI_GR_PREVIEW_PUBLISH") == "yes"
    if publish:
        receipt = publish_preview(root, source_folder=folder)
        print("[favi-gr-preview] " + json.dumps(receipt, sort_keys=True), flush=True)
    return report


if __name__ == "__main__":
    print(json.dumps(execute(batch_limit=int(os.getenv("FEED_GR_PAGE_LIMIT", "10")))))

