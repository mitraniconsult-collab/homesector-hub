"""Resumable, read-only census of Shopify standard Product category for FAVI.

Stores a separate mapping by product handle; does not change Shopify records,
feed data, or Google BG journal. Page commits are durable and atomic.
"""
import json
import os
from collections import Counter
from pathlib import Path
from .markets_catalog import shopify_post
from .shopify_auth import get_admin_token

QUERY = """
query FaviCategories($cursor: String) {
  products(first: 50, after: $cursor, sortKey: ID) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id handle status productType
      category { id fullName }
    }
  }
}
"""

def scan(mount, page_limit=400):
    root = Path(mount) / "favi-shopify-categories"
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    journal_path = root / "products.jsonl"
    if manifest_path.exists():
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not journal_path.exists() or journal_path.stat().st_size < meta["bytes"]:
            raise RuntimeError("FAVI category checkpoint missing/truncated")
    else:
        if journal_path.exists():
            raise RuntimeError("Orphaned category journal")
        meta = {"cursor": None, "count": 0, "bytes": 0, "finished": False}
    if not meta["finished"]:
        store = os.environ.get("SHOPIFY_STORE", "").strip()
        if not store.endswith(".myshopify.com") or "/" in store:
            raise ValueError("Invalid Shopify store")
        token = get_admin_token(store)
        endpoint = f"https://{store}/admin/api/2026-07/graphql.json"
        for _ in range(page_limit):
            payload = shopify_post(endpoint, token, {
                "query": QUERY, "variables": {"cursor": meta["cursor"]}})
            if payload.get("errors") or not (payload.get("data") or {}).get("products"):
                raise RuntimeError("Shopify category read denied or query invalid")
            page = payload["data"]["products"]
            new_cursor = page["pageInfo"]["endCursor"]
            if page["pageInfo"]["hasNextPage"] and (not new_cursor or new_cursor == meta["cursor"]):
                raise RuntimeError("Invalid category pagination cursor")
            with journal_path.open("a+b") as f:
                f.truncate(meta["bytes"])
                f.seek(meta["bytes"])
                for product in page["nodes"]:
                    f.write((json.dumps({
                        "handle": product["handle"],
                        "status": product["status"],
                        "category_id": (product.get("category") or {}).get("id"),
                        "category_name": (product.get("category") or {}).get("fullName"),
                        "product_type": product.get("productType"),
                    }, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
                byte_pos = f.tell()
            new_meta = {
                "cursor": new_cursor,
                "count": meta["count"] + len(page["nodes"]),
                "bytes": byte_pos,
                "finished": not page["pageInfo"]["hasNextPage"],
            }
            tmp = root / "manifest.tmp"
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(new_meta, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, manifest_path)
            meta = new_meta
            if meta["count"] % 1000 == 0 or meta["finished"]:
                print(f"[favi-shopify] checkpoint_products={meta['count']} finished={meta['finished']}", flush=True)
            if meta["finished"]:
                break
    if not meta["finished"]:
        return {"status": "incomplete", "products": meta["count"], "published": False}
    types = Counter()
    missing = 0
    with journal_path.open(encoding="utf-8") as fh:
        for line in fh:
            item = json.loads(line)
            category = item.get("category_name")
            if category:
                types[category] += 1
            else:
                missing += 1
    report = {
        "status": "complete", "shopify_products": meta["count"],
        "with_standard_category": meta["count"] - missing,
        "missing_standard_category": missing,
        "distinct_categories": len(types),
        "top_standard_categories": types.most_common(30),
        "published": False,
    }
    path = root / "category-census.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report
