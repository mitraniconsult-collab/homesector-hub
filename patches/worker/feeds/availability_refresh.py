"""Read current variant policy and arrival dates for the private BG snapshot.

Only Shopify queries are used. The original catalog journal/XML is retained.
"""
import hashlib
import json
import os
import time
from decimal import Decimal, InvalidOperation
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
      id displayName inventoryQuantity inventoryPolicy
      price_BG: contextualPricing(context: {country: BG}) { price { amount currencyCode } }
      expectedArrival: metafield(namespace: "custom", key: "expected_arrival") { value }
      product {
        variantsCount { count }
        expectedArrival: metafield(namespace: "custom", key: "expected_arrival") { value }
      }
    }
  }
}'''


def read_nodes(endpoint, token, ids):
    # GraphQL throttling can be returned with HTTP 200, so the common HTTP
    # retry helper alone is insufficient for this batched read.
    for attempt in range(6):
        response = shopify_post(endpoint, token, {"query": QUERY, "variables": {"ids": ids}})
        errors = response.get("errors") or []
        if errors and all((error.get("extensions") or {}).get("code") == "THROTTLED"
                          for error in errors) and attempt < 5:
            cost = (response.get("extensions") or {}).get("cost") or {}
            throttle = cost.get("throttleStatus") or {}
            needed = cost.get("requestedQueryCost", 500)
            available = throttle.get("currentlyAvailable", 0)
            rate = throttle.get("restoreRate", 50)
            delay = max(1, (needed - available) / max(1, rate) + 0.25)
            time.sleep(min(60, delay))
            continue
        nodes = (response.get("data") or {}).get("nodes")
        if errors or not isinstance(nodes, list) or len(nodes) != len(ids):
            raise RuntimeError("Shopify availability read failed")
        return nodes
    raise RuntimeError("Shopify availability retry limit reached")


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


def apply_current_offer(row, node):
    """Refresh the BG offer together with inventory; reject incomplete pricing."""
    if node is None:
        return row
    money = (node.get("price_BG") or {}).get("price") or {}
    title = node.get("displayName")
    try:
        amount = Decimal(str(money.get("amount", "")))
    except InvalidOperation:
        raise RuntimeError("Incomplete Shopify BG price") from None
    if (not amount.is_finite() or amount <= 0 or money.get("currencyCode") != "EUR"
            or not isinstance(title, str) or not title.strip()):
        raise RuntimeError("Invalid Shopify BG offer")
    return {**row, "price": str(money["amount"]), "currency": "EUR",
            "title": title.removesuffix(" - Default Title").strip()}


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
        nodes = read_nodes(endpoint, token, ids)
        for row, node in zip(batch, nodes):
            if node is not None and node.get("id") != row["id"]:
                raise RuntimeError("Mismatched Shopify variant response")
            updated = apply_current_offer(apply_source(row, node), node)
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
