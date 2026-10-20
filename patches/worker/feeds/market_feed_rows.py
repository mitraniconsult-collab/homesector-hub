"""Join Shopify source catalog, verified translations and feed quality checks.

Read-only preparation. International URLs must be verified by the caller, not
derived from a translated title or guessed from the base Shopify handle.
"""
from collections import Counter
from .channel_quality import check_product
from .localization import apply_verified_translations
from .markets_normalize import normalize_market
from .shopify_translations import fetch_translations
from .targets import enabled

def prepare_market_rows(products, market, channel, verified_url_ids=None,
                        translated_map=None):
    if not enabled(channel, market):
        raise ValueError("Unsupported market-channel target")
    products = list(products)
    verified_url_ids = set(verified_url_ids or [])
    if market != "BG" and translated_map is None:
        translated_map = fetch_translations([p["id"] for p in products])
    translations = translated_map or {}
    accepted, reasons, seen = [], Counter(), set()
    for product in products:
        rows = normalize_market(product, market)
        if not rows:
            reasons["not_published_or_incomplete_source"] += 1
        translated = translations.get(product.get("id"), {})
        for row in rows:
            row = apply_verified_translations(
                row, translated.get(market, []), market,
                url_verified=(product["id"] in verified_url_ids))
            issues = check_product(row, market, channel)
            if not row.get("id") or row["id"] in seen:
                issues.append("duplicate_or_missing_variant_id")
            if issues:
                reasons.update(set(issues))
                continue
            seen.add(row["id"])
            accepted.append(row)
    return accepted, dict(sorted(reasons.items()))
