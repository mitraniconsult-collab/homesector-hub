"""Stable IDs for feed exports without altering Shopify identifiers.

Shopify GIDs are internal references. FAVI requires IDs consisting of letters,
digits, underscores and hyphens. Prefix numeric variant IDs to avoid collisions
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
    return "shopify-v" + match.group(1)

def group_feed_id(value):
    match = _PRODUCT_GID.fullmatch(str(value or ""))
    if not match:
        raise ValueError("Invalid Shopify Product GID")
    return "shopify-p" + match.group(1)

def is_safe_favi_id(value):
    return bool(_SAFE.fullmatch(str(value or "")))

def export_ids(row, product_gid):
    output = dict(row)
    output["id"] = variant_feed_id(row.get("id"))
    output["item_group_id"] = group_feed_id(product_gid)
    return output
