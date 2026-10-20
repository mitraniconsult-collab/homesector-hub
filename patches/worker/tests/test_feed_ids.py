import pytest
from feeds.feed_ids import export_ids, group_feed_id, is_safe_favi_id, variant_feed_id

def test_variant_feed_id_stable_and_platform_safe():
    first = variant_feed_id("gid://shopify/ProductVariant/1122334455")
    assert first == "shopify-v1122334455"
    assert is_safe_favi_id(first)
    assert variant_feed_id("gid://shopify/ProductVariant/1122334455") == first

def test_variant_and_group_have_different_namespaces():
    assert variant_feed_id("gid://shopify/ProductVariant/1") != group_feed_id("gid://shopify/Product/1")

def test_invalid_internal_id_does_not_silently_publish():
    for bad in ("", None, "sku/12", "gid://shopify/Product/12", "gid://shopify/ProductVariant/11?extra=2"):
        with pytest.raises(ValueError):
            variant_feed_id(bad)

def test_export_grouping():
    row = export_ids({"id": "gid://shopify/ProductVariant/17"}, "gid://shopify/Product/12")
    assert row["id"] == "shopify-v17"
    assert row["item_group_id"] == "shopify-p12"
