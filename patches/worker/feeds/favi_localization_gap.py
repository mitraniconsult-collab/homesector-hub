"""Aggregate missing market copy by reviewed Shopify category for feed triage."""
from collections import Counter


def gaps_by_taxonomy(products, categories, translated_map, market, limit=30):
    gaps = Counter()
    missing_keys = Counter()
    for product in products:
        pid = product["id"]
        if pid not in categories:
            continue
        keys = {entry.get("key") for entry in
                translated_map.get(pid, {}).get(market, []) if entry.get("value")}
        missing = {"title", "body_html"} - keys
        if missing:
            taxonomy = (product.get("category") or {}).get("id") or "unclassified"
            gaps[taxonomy] += 1
            missing_keys.update(missing)
    return {"products": sum(gaps.values()),
            "missing_keys": dict(sorted(missing_keys.items())),
            "top_taxonomy": gaps.most_common(limit)}
