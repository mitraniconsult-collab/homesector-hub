"""Bounded, restartable Google BG feed job, not an ASGI startup thread.

Requires a separately provisioned durable mounted volume and configured
Shopify read-only credentials. Each complete Shopify page is committed before
advancing its cursor. No feed is published externally.
"""
import json
import os
import time
from pathlib import Path
from xml.etree import ElementTree as ET
from .config import eligible
from .durable_journal import DurableJournal
from .markets_catalog import catalog_query, read_remaining_variants, shopify_post
from .markets_normalize import normalize_market
from .shopify_auth import get_admin_token
from .xml_export import generate

def post_graphql(url, token, query, variables):
    for attempt in range(6):
        payload = shopify_post(url, token, {"query": query, "variables": variables})
        errors = payload.get("errors") or []
        if errors and all((e.get("extensions") or {}).get("code") == "THROTTLED" for e in errors) and attempt < 5:
            cost = (payload.get("extensions") or {}).get("cost") or {}
            throttle = cost.get("throttleStatus") or {}
            delay = (cost.get("requestedQueryCost", 500) - throttle.get("currentlyAvailable", 0)) / max(1, throttle.get("restoreRate", 50))
            time.sleep(min(60, max(1, delay + .25)))
            continue
        if errors or not payload.get("data"):
            raise RuntimeError("Shopify GraphQL query rejected")
        return payload["data"]


def execute(batch_limit=100, root=None, store=None, token=None, bg_only=False, should_stop=lambda: False):
    if not isinstance(batch_limit, int) or not 1 <= batch_limit <= 1000:
        raise ValueError("batch_limit must be 1..1000")
    root = root or os.environ.get("FEED_DURABLE_PATH")
    if not root:
        raise ValueError("Durable mount path is not configured")
    journal = DurableJournal(Path(root) / "google-bg")
    if journal.manifest.exists():
        old = json.loads(journal.manifest.read_text(encoding="utf-8"))
    else:
        old = {"cursor": None, "products": 0, "items": 0,
               "bytes": 0, "finished": False}
    if old["finished"]:
        return finalize(journal)
    store = store or os.environ.get("SHOPIFY_STORE", "")
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify hostname")
    token = token or get_admin_token(store)
    url = f"https://{store}/admin/api/2026-07/graphql.json"
    cursor = old["cursor"]
    seen_cursors = set()
    for _ in range(batch_limit):
        if should_stop():
            break
        if cursor is not None and cursor in seen_cursors:
            raise RuntimeError("Repeated Shopify pagination cursor")
        seen_cursors.add(cursor)
        data = post_graphql(url, token, catalog_query(bg_only=bg_only), {"cursor": cursor})
        page = data["products"]
        page_rows = []
        for product in page["nodes"]:
            if (product.get("variants") or {}).get("pageInfo", {}).get("hasNextPage"):
                variants = product["variants"]
                variants["nodes"].extend(read_remaining_variants(
                    url, token, product["id"], variants["pageInfo"]["endCursor"], bg_only=bg_only))
            for row in normalize_market(product, "BG"):
                if eligible(row, "BG"):
                    page_rows.append(row)
        end = page["pageInfo"]["endCursor"]
        has_more = bool(page["pageInfo"]["hasNextPage"])
        if not end and has_more:
            raise RuntimeError("Shopify returned missing pagination cursor")
        if not page["nodes"] and has_more:
            raise RuntimeError("Empty Shopify page with hasNextPage")
        new_count = old["products"] + len(page["nodes"])
        old = journal.append_page(end, page_rows, new_count, finished=not has_more)
        cursor = end
        print(f"[feeds-job] checkpoint products={new_count} items={old['items']}", flush=True)
        if not has_more:
            return finalize(journal)
    return {"status": "incomplete", "products": old["products"],
            "items": old["items"], "cursor_saved": True,
            "published": False}

def finalize(journal):
    meta, rows = journal.load()
    if not meta.get("finished"):
        raise RuntimeError("Attempted to finalize incomplete Shopify catalog")
    xml = generate(rows, "BG", "google")
    root = ET.fromstring(xml)
    count = len(root.findall("./channel/item"))
    if count != len(rows):
        raise RuntimeError("Feed item count mismatch")
    import hashlib
    digest = hashlib.sha256(xml).hexdigest()
    temp = journal.root / "google-bg.xml.tmp"
    output = journal.root / "google-bg-unpublished.xml"
    with temp.open("wb") as fh:
        fh.write(xml)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temp, output)
    print(f"[feeds-job] COMPLETE products={meta['products']} items={count} sha256={digest}", flush=True)
    return {"status": "completed", "products": meta["products"],
            "items": count, "sha256": digest, "published": False}

if __name__ == "__main__":
    print(json.dumps(execute(batch_limit=int(os.getenv("FEED_JOB_PAGE_LIMIT", "100")))))
