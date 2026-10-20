"""Unit tests for independent, fail-closed channel preflight."""
from feeds.channel_quality import audit, check_product

BASE = {
    "id": "gid://shopify/ProductVariant/1",
    "title": "Тестов продукт",
    "description": "Описание",
    "link": "https://homesector.bg/products/test?variant=1",
    "image_link": "https://cdn.shopify.com/test.jpg",
    "price": "25.00", "currency": "EUR",
    "active": True, "published": True, "markets": ["BG"],
    "available": True, "continue_selling": False,
    "product_type": "Мебели",
}

def test_google_bg_passes():
    assert check_product(BASE, "BG", "google") == []

def test_missing_favi_category_is_rejected():
    row = {**BASE, "product_type": ""}
    assert "missing_favi_category" in check_product(row, "BG", "favi")

def test_unverified_ro_localization_never_publishes():
    row = {**BASE, "markets": ["RO"], "currency": "RON",
           "link": "https://homesector.ro/products/test?variant=1"}
    issues = check_product(row, "RO", "google")
    assert "unverified_localized_copy" in issues
    assert "unverified_market_url" in issues

def test_duplicate_variants_excluded():
    report = audit([BASE, BASE], "BG", "meta")
    assert report["eligible"] == 1
    assert report["excluded"] == 1
    assert report["issues"]["duplicate_or_missing_id"] == 1

def test_wrong_currency_never_passes():
    row = {**BASE, "currency": "BGN"}
    assert "wrong_currency" in check_product(row, "BG", "google")

def test_unsupported_biano_market():
    try:
        check_product(BASE, "RO", "biano")
    except ValueError:
        return
    raise AssertionError("Biano RO must not be enabled")

def test_favi_requires_platform_validated_category_even_for_bg():
    row = {**BASE, "product_type": "Мебели"}
    assert "unverified_favi_category" in check_product(row, "BG", "favi")
    row["category_verified_for_market"] = True
    assert "unverified_favi_category" not in check_product(row, "BG", "favi")
