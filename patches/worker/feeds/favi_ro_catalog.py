"""Checkpointed, private FAVI Romania source scan and preview.

Run only on the confirmed durable feed volume. This module does not publish a
public URL or alter the live Greek generation.
"""
import hashlib
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .batch_job import post_graphql
from .durable_journal import DurableJournal
from .favi_ro_preview import create_preview
from .favi_ro_taxonomy import categories_for_products
from .favi_gr_urls import verify_market_urls
from .favi_ro_finalize import collect
from .markets_catalog import catalog_query, read_remaining_variants
from .shopify_auth import get_admin_token
from .shopify_translations import fetch_translations, fetch_variant_translations
from .xml_audit import validate_xml


def execute(batch_limit=10, root=None, store=None, token=None,
            should_stop=lambda: False, source_folder=None, deadline=None):
    if not isinstance(batch_limit, int) or not 1 <= batch_limit <= 1000:
        raise ValueError("batch_limit must be 1..1000")
    root = root or os.getenv("FEED_DURABLE_PATH")
    if not root:
        raise ValueError("Durable mount path is not configured")
    journal = DurableJournal(source_folder or Path(root) / "favi-ro-source")
    meta, _ = journal.load()
    if meta["finished"]:
        return finalize(journal, store=store, token=token, deadline=deadline,
                        should_stop=should_stop)
    store = store or os.getenv("SHOPIFY_STORE", "")
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify hostname")
    token = token or get_admin_token(store)
    url = f"https://{store}/admin/api/2026-07/graphql.json"
    cursor = meta["cursor"]
    seen = set()
    for _ in range(batch_limit):
        if should_stop() or deadline is not None and time.time() >= deadline:
            break
        if cursor is not None and cursor in seen:
            raise RuntimeError("Repeated Shopify pagination cursor")
        seen.add(cursor)
        page = post_graphql(url, token, catalog_query(ro_only=True), {"cursor": cursor})["products"]
        nodes = page["nodes"]
        for product in nodes:
            variants = product["variants"]
            if variants["pageInfo"]["hasNextPage"]:
                variants["nodes"].extend(read_remaining_variants(
                    url, token, product["id"], variants["pageInfo"]["endCursor"],
                    ro_only=True))
                variants["pageInfo"]["hasNextPage"] = False
        end = page["pageInfo"]["endCursor"]
        more = bool(page["pageInfo"]["hasNextPage"])
        if (more and (not nodes or not end or end == cursor)) or (not more and not nodes):
            raise RuntimeError("Invalid Shopify catalog page")
        meta = journal.append_page(end, nodes, meta["products"] + len(nodes),
                                   finished=not more)
        cursor = end
        print(f"[favi-ro-scan] checkpoint products={meta['products']}", flush=True)
        if not more:
            return finalize(journal, store=store, token=token, deadline=deadline,
                            should_stop=should_stop)
    return {"status": "incomplete", "source_products": meta["products"],
            "cursor_saved": True, "published": False}


def finalize(journal, store=None, token=None, deadline=None,
             should_stop=lambda: False):
    meta, products = journal.load()
    if not meta["finished"] or len(products) != meta["products"]:
        raise RuntimeError("Incomplete Romanian source catalog")
    romanian = [p for p in products if p.get("published_RO") is True
                and p.get("status") == "ACTIVE"]
    categories = categories_for_products(romanian)
    store = store or os.getenv("SHOPIFY_STORE", "")
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify hostname")
    token = token or get_admin_token(store)
    if deadline is not None:
        collected = collect(journal, romanian, categories, store, token,
                            deadline, should_stop)
        if collected["status"] == "yielded":
            return {"status": "yielded", "stage": collected["stage"],
                    "source_products": meta["products"], "published": False}
        translated = collected["translated_map"]
        verified = collected["verified_urls"] | collected["collection_urls"]
        url_check = collected["url_check"]
        collection_check = collected["collection_check"]
        variants = collected["variant_map"]
    else:
        translated = fetch_translations(list(categories), store=store, token=token, market="RO")
        verified, url_check = verify_market_urls(
            romanian, categories, translated_map=translated, market="RO")
        variant_ids = [v["id"] for p in romanian if p["id"] in verified
                       for v in p["variants"]["nodes"] if v.get("selectedOptions")]
        variants = fetch_variant_translations(variant_ids, "RO", store=store, token=token)
        collection_check = {"checked": 0, "verified": 0, "without_collection": 0}
    for product in romanian:
        if product["id"] in verified:
            product["verified_market_url_RO"] = verified[product["id"]]
    if should_stop() or deadline is not None and time.time() >= deadline:
        return {"status": "yielded", "stage": "serialize",
                "source_products": meta["products"], "published": False}
    xml, report = create_preview(romanian, categories, set(verified), translated,
                                 variants)
    report.update({
        "source_complete": True,
        "source_snapshot_at": datetime.fromtimestamp(
            journal.manifest.stat().st_mtime, timezone.utc).isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "romanian_published_products": len(romanian),
        "romanian_published_variants": sum(len(p["variants"]["nodes"]) for p in romanian),
        "mapped_category_products": len(categories),
        "verified_market_url_products": len(verified),
        "verified_url_check": url_check,
        "verified_collection_url_check": collection_check,
        "localized_copy_products_in_mapped_categories": sum(
            {"title", "body_html"}.issubset({
                entry.get("key") for entry in translated.get(pid, {}).get("RO", [])
                if entry.get("value")}) for pid in categories),
        "top_shopify_taxonomy": Counter(
            ((p.get("category") or {}).get("id"),
             (p.get("category") or {}).get("fullName"))
            for p in romanian if p.get("category")).most_common(50),
        "sha256": hashlib.sha256(xml).hexdigest(),
    })
    if report["xml_items"]:
        audit = validate_xml(xml, "RO", max_issues=0)
        if audit["items"] != report["xml_items"] or audit["unique_ids"] != audit["items"]:
            raise RuntimeError("Romanian preview audit failed")
    folder = journal.root
    for name, data in (("favi-ro-private.xml", xml),
                       ("favi-ro-report.json", json.dumps(
                           report, ensure_ascii=False, indent=2).encode())):
        temporary = folder / (name + ".tmp")
        with temporary.open("wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, folder / name)
    print("[favi-ro-scan] " + json.dumps(report, sort_keys=True), flush=True)
    return report


if __name__ == "__main__":
    print(json.dumps(execute(batch_limit=int(os.getenv("FEED_RO_PAGE_LIMIT", "10")))))
