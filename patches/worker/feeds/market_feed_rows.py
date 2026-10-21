"""Join Shopify source catalog, verified translations and feed quality checks.

Read-only preparation. International URLs must be verified by the caller, not
derived from a translated title or guessed from the base Shopify handle.
"""
from collections import Counter
from .channel_quality import check_product
from .localization import apply_verified_translations, localize_variant_color
from .markets_normalize import normalize_market
from .shopify_translations import fetch_translations, fetch_variant_translations
from .targets import enabled
from .feed_ids import export_ids

def prepare_market_rows(products, market, channel, verified_url_ids=None,
                        translated_map=None, translated_variant_map=None,
                        category_by_product=None):
    if not enabled(channel, market):
        raise ValueError("Unsupported market-channel target")
    products = list(products)
    verified_url_ids = set(verified_url_ids or [])
    if market != "BG" and translated_map is None:
        translation_ids = ([p["id"] for p in products if p.get("id") in verified_url_ids]
                           if market == "GR" and channel == "favi"
                           else [p["id"] for p in products])
        translated_map = fetch_translations(translation_ids, market=market)
    translations = translated_map or {}
    if market == "GR" and channel == "favi" and translated_variant_map is None:
        ids = [v["id"] for p in products if p.get("id") in verified_url_ids
               for v in (p.get("variants") or {}).get("nodes", [])
               if v.get("id") and any(str(o.get("name", "")).casefold() in
                                      ("color", "colour", "цвят", "цвет")
                                      for o in v.get("selectedOptions") or [])]
        translated_variant_map = fetch_variant_translations(ids, market)
    translated_variant_map = translated_variant_map or {}
    category_by_product = category_by_product or {}
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
            if market == "GR" and channel == "favi":
                row = localize_variant_color(
                    row, translated_variant_map.get(row["id"], []), market)
            if channel == "favi":
                category = category_by_product.get(product["id"], {})
                if (category.get("market") == market and category.get("verified") is True
                        and str(category.get("path") or "").strip()):
                    row["product_type"] = category["path"].strip()
                    row["category_verified_for_market"] = True
                else:
                    row["product_type"] = None
                    row["category_verified_for_market"] = False
            row = export_ids(row, product["id"])
            issues = check_product(row, market, channel)
            if not row.get("id") or row["id"] in seen:
                issues.append("duplicate_or_missing_variant_id")
            if issues:
                reasons.update(set(issues))
                continue
            seen.add(row["id"])
            accepted.append(row)
    return accepted, dict(sorted(reasons.items()))
