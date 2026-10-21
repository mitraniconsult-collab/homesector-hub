"""Restartable private FAVI Greece catalog scan and quality report.

Run on the confirmed durable feed mount. This never publishes a destination URL.
The operator-supplied JSON files contain checked product GIDs for Greek landing
pages and per-product Greek categories; absent files are treated as empty gates.
"""
import hashlib
import json
import os
from pathlib import Path

from .batch_job import post_graphql
from .durable_journal import DurableJournal
from .favi_gr_preview import create_preview
from .markets_catalog import catalog_query, read_remaining_variants
from .shopify_auth import get_admin_token
from .xml_audit import validate_xml


def _inputs(root):
    root = Path(root)
    categories_path = root / "favi-gr-verified-categories.json"
    urls_path = root / "favi-gr-verified-url-ids.json"
    categories = json.loads(categories_path.read_text(encoding="utf-8")) if categories_path.exists() else {}
    urls = json.loads(urls_path.read_text(encoding="utf-8")) if urls_path.exists() else []
    if not isinstance(categories, dict) or not isinstance(urls, list):
        raise ValueError("Invalid Greek verification files")
    return categories, urls


def execute(batch_limit=10, root=None, store=None, token=None, should_stop=lambda: False):
    if not isinstance(batch_limit, int) or not 1 <= batch_limit <= 1000:
        raise ValueError("batch_limit must be 1..1000")
    root = root or os.environ.get("FEED_DURABLE_PATH")
    if not root:
        raise ValueError("Durable mount path is not configured")
    journal = DurableJournal(Path(root) / "favi-gr-source")
    meta, _ = journal.load()
    if meta["finished"]:
        return finalize(journal, root, store=store, token=token)
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
            return finalize(journal, root, store=store, token=token)
    return {"status": "incomplete", "source_products": meta["products"],
            "cursor_saved": True, "published": False}


def finalize(journal, root, store=None, token=None):
    meta, products = journal.load()
    if not meta["finished"] or len(products) != meta["products"]:
        raise RuntimeError("Incomplete Greek source catalog")
    categories, urls = _inputs(root)
    greek_products = [p for p in products if p.get("published_GR") is True
                      and p.get("status") == "ACTIVE"]
    xml, report = create_preview(greek_products, categories, urls)
    report["source_products"] = meta["products"]
    report["greek_published_products"] = len(greek_products)
    report["source_complete"] = True
    report["sha256"] = hashlib.sha256(xml).hexdigest()
    if report["xml_items"]:
        audit = validate_xml(xml, "GR", max_issues=0)
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
    return report


if __name__ == "__main__":
    print(json.dumps(execute(batch_limit=int(os.getenv("FEED_GR_PAGE_LIMIT", "10")))))
