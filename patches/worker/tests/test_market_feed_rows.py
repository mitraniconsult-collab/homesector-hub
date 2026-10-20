"""Regression tests for international feed rows and fail-closed localization."""
from feeds.market_feed_rows import prepare_market_rows

def sample_product():
    return {
        "id": "gid://shopify/Product/1", "status": "ACTIVE",
        "published_RO": True, "handle": "pan",
        "title": "Тиган", "descriptionHtml": "<p>Описание</p>",
        "vendor": "Quttin", "productType": "Тигани",
        "featuredImage": {"url": "https://cdn.shopify.com/pan.jpg"},
        "variants": {"nodes": [{
            "id": "gid://shopify/ProductVariant/11", "sku": "PAN1",
            "barcode": "1234567890123", "inventoryQuantity": 5,
            "inventoryPolicy": "DENY", "image": None,
            "price_RO": {"price": {"amount": "182", "currencyCode": "RON"}},
        }]},
    }

def test_ro_missing_verified_url_is_rejected():
    product = sample_product()
    translations = {product["id"]: {"RO": [
        {"key": "title", "value": "Tigaie Quttin"},
        {"key": "body_html", "value": "<p>Tigaie aluminiu</p>"},
    ]}}
    rows, reasons = prepare_market_rows(
        [product], "RO", "meta", translated_map=translations)
    assert rows == []
    assert reasons["unverified_market_url"] == 1

def test_ro_verified_url_and_translations_pass():
    product = sample_product()
    translations = {product["id"]: {"RO": [
        {"key": "title", "value": "Tigaie Quttin"},
        {"key": "body_html", "value": "<p>Tigaie aluminiu</p>"},
    ]}}
    rows, reasons = prepare_market_rows(
        [product], "RO", "meta", translated_map=translations,
        verified_url_ids={product["id"]})
    assert reasons == {}
    assert len(rows) == 1
    assert rows[0]["title"] == "Tigaie Quttin"
    assert rows[0]["description"] == "Tigaie aluminiu"

def test_ro_missing_translation_is_rejected():
    product = sample_product()
    rows, reasons = prepare_market_rows(
        [product], "RO", "google",
        translated_map={product["id"]: {"RO": []}},
        verified_url_ids={product["id"]})
    assert rows == []
    assert reasons["unverified_localized_copy"] == 1
