"""Keep storefront requests for products that can pass the locale gate."""


def has_localized_copy(translated_map, product_id, market):
    entries = (translated_map.get(product_id) or {}).get(market) or []
    values = {entry.get("key"): str(entry.get("value") or "").strip()
              for entry in entries if isinstance(entry, dict)}
    return bool(values.get("title") and values.get("body_html"))
