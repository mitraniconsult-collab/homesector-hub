"""Stable IDs for feed exports without altering Shopify identifiers.

Shopify GIDs are internal references. FAVI requires IDs consisting of letters,
and digits, hyphens and underscores. Prefix numeric variant IDs to avoid collisions
with other identifier types. Keep mapping stable across regenerations.
"""
import re

_VARIANT_GID = re.compile(r"^gid://shopify/ProductVariant/([1-9][0-9]*)$")
_PRODUCT_GID = re.compile(r"^gid://shopify/Product/([1-9][0-9]*)$")
_SAFE = re.compile(r"^[a-zA-Z0-9_-]+$")

def variant_feed_id(value):
    match = _VARIANT_GID.fullmatch(str(value or ""))
    if not match:
        raise ValueError("Invalid Shopify ProductVariant GID")
    return "shopifyv" + match.group(1)

def group_feed_id(value):
    match = _PRODUCT_GID.fullmatch(str(value or ""))
    if not match:
        raise ValueError("Invalid Shopify Product GID")
    return "shopifyp" + match.group(1)

def is_safe_favi_id(value):
    return bool(_SAFE.fullmatch(str(value or "")))

def export_ids(row, product_gid, historical_favi_ids=None):
    output = dict(row)
    original = str(row.get("id") or "")
    historical = (historical_favi_ids or {}).get(original)
    if historical is not None:
        if not is_safe_favi_id(historical):
            raise ValueError("Invalid historical FAVI ID; migration review required")
        output["id"] = str(historical)
    else:
        output["id"] = variant_feed_id(original)
    output["item_group_id"] = group_feed_id(product_gid)
    return output
