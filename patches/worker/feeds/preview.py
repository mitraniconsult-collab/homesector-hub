"""Safe feed preview and diagnostics without changing Shopify."""
from collections import Counter
from .config import MARKETS
from .markets_normalize import normalize_market
from .xml_export import generate

def preview(catalog, country, channel, sample_limit=10):
    if country not in MARKETS:
        raise ValueError("Unsupported market")
    records = list(catalog)
    rows = []
    reasons = Counter()
    for product in records:
        normalized = normalize_market(product, country)
        if not normalized:
            reasons["not_published_or_incomplete"] += 1
        rows.extend(normalized)
    seen = set()
    unique = []
    for row in rows:
        if not row.get("id") or row["id"] in seen:
            reasons["duplicate_or_missing_variant_id"] += 1
            continue
        seen.add(row["id"])
        unique.append(row)
    xml = generate(unique, country, channel)
    from xml.etree import ElementTree as ET
    count = len(ET.fromstring(xml).findall("./channel/item"))
    return {
        "market": country, "channel": channel,
        "products_scanned": len(records), "variants_normalized": len(unique),
        "items_exported": count, "excluded_summary": dict(reasons),
        "sample_skus": [p.get("mpn") for p in unique[:sample_limit]],
        "xml": xml,
    }
