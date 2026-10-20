"""Read current variant policy and arrival dates for the private BG snapshot.

Only Shopify queries are used. The original catalog journal/XML is retained.
"""
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .availability import arrival_timestamp, feed_availability
from .markets_catalog import shopify_post
from .shopify_auth import get_admin_token
from .xml_export import generate

QUERY = '''query FeedAvailability($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on ProductVariant {
      id inventoryQuantity inventoryPolicy
      expectedArrival: metafield(namespace: "custom", key: "expected_arrival") { value }
      product {
        variantsCount { count }
        expectedArrival: metafield(namespace: "custom", key: "expected_arrival") { value }
      }
    }
  }
}'''


def apply_source(row, node):
    row = dict(row)
    row.pop("availability", None)
    if node is None:
        row.update(available=False, continue_selling=False, expected_arrival=None,
                   availability_date=None, availability="out_of_stock")
        return row
    quantity, policy = node.get("inventoryQuantity"), node.get("inventoryPolicy")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or policy not in ("CONTINUE", "DENY"):
        raise RuntimeError("Incomplete Shopify inventory source")
    arrival = (node.get("expectedArrival") or {}).get("value")
    product = node.get("product") or {}
    # Never copy one product-level colour's date onto other variants.
    if not arrival and (product.get("variantsCount") or {}).get("count") == 1:
        arrival = (product.get("expectedArrival") or {}).get("value")
    row.update(available=quantity > 0, inventory_quantity=quantity,
               continue_selling=policy == "CONTINUE", expected_arrival=arrival,
               availability_date=arrival_timestamp(arrival))
    row["availability"] = feed_availability(row)
    return row


def refresh(mount):
    root = Path(mount)
    if os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes" or not os.path.ismount(root):
        raise RuntimeError("Confirmed mounted storage required")
    folder = root / "google-bg"
    manifest = json.loads((folder / "manifest.json").read_text())
    if not manifest.get("finished"):
        return {"status": "awaiting_complete_catalog", "published": False}
    records = (folder / "records.jsonl").read_bytes()
    if len(records) != manifest["bytes"]:
        raise RuntimeError("Catalog journal size mismatch")
    rows = [json.loads(line) for line in records.splitlines()]
    if len(rows) != manifest["items"]:
        raise RuntimeError("Catalog journal count mismatch")
    store = os.environ.get("SHOPIFY_STORE", "").strip()
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify store")
    token = get_admin_token(store)
    endpoint = f"https://{store}/admin/api/2026-07/graphql.json"
    output, counts = [], Counter()
    for start in range(0, len(rows), 100):
        batch = rows[start:start + 100]
        ids = [row["id"] for row in batch]
        response = shopify_post(endpoint, token, {"query": QUERY, "variables": {"ids": ids}})
        nodes = (response.get("data") or {}).get("nodes")
        if response.get("errors") or not isinstance(nodes, list) or len(nodes) != len(batch):
            raise RuntimeError("Shopify availability read failed")
        for row, node in zip(batch, nodes):
            if node is not None and node.get("id") != row["id"]:
                raise RuntimeError("Mismatched Shopify variant response")
            updated = apply_source(row, node)
            output.append(updated)
            counts[updated["availability"]] += 1
            if not updated["available"] and updated["continue_selling"]:
                counts["zero_stock_continue_included"] += 1
        if start % 1000 == 0:
            print(f"[feed-availability] refreshed={len(output)}", flush=True)
    # Finish every read before atomically replacing either private candidate.
    artifacts = {
        folder / "availability-corrected-records.jsonl": b"".join(
            (json.dumps(row, ensure_ascii=False) + "\n").encode() for row in output),
        folder / "google-bg-corrected-unpublished.xml": generate(output, "BG", "google"),
    }
    for path, data in artifacts.items():
        temp = path.with_suffix(".tmp")
        with temp.open("wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    return {"status": "corrected_unpublished_snapshot", "source_items": len(rows),
            "availability_counts": dict(counts), "published": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(artifacts[folder / "google-bg-corrected-unpublished.xml"]).hexdigest()}
