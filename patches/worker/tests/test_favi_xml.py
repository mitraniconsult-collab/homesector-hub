"""Static guard tests for FAVI platform-specific XML requirements."""
from xml.etree import ElementTree as ET
import pytest
from feeds.favi_xml import generate_favi, validate

BASE = {
    "id": "shopifyv17", "item_group_id": "shopifyp12", "title": "Маса",
    "description": "Дървена маса", "link": "https://homesector.bg/products/masa?variant=17",
    "image_link": "https://cdn.shopify.com/a.jpg", "price": "54.00",
    "currency": "EUR", "active": True, "published": True, "markets": ["BG"],
    "available": True, "continue_selling": False, "brand": "Atmosphera",
    "product_type": "Мебели > Маси", "category_verified_for_market": True,
}

def test_favi_bg_serialization_is_parseable():
    data, report = generate_favi([BASE], "BG")
    root = ET.fromstring(data)
    assert len(root.findall("./channel/item")) == 1
    assert report["items_exported"] == 1
    assert report["published"] is False

def test_favi_rejects_missing_market_category():
    row = {**BASE, "category_verified_for_market": False}
    assert "unverified_favi_category" in validate(row, "BG")

def test_favi_requires_date_for_backorder():
    row = {**BASE, "available": False, "continue_selling": True, "availability": "backorder"}
    assert "invalid_backorder_availability_date" in validate(row, "BG")
    row["availability_date"] = "2026-11-25T13:00:00+02:00"
    assert "invalid_backorder_availability_date" not in validate(row, "BG")

def test_favi_rejects_special_characters_in_ids():
    row = {**BASE, "id": "shopify-v17"}
    assert "invalid_favi_alphanumeric_id" in validate(row, "BG")

def test_favi_duplicate_url_prevents_catalog_merge():
    rows = [BASE, {**BASE, "id": "shopifyv18"}]
    data, report = generate_favi(rows, "BG")
    assert report["items_exported"] == 1
    assert report["excluded_reasons"]["duplicate_or_missing_url"] == 1


def test_color_variants_share_group_but_keep_unique_offer_ids():
    second = {**BASE, "id": "shopifyv18", "color": "Син",
              "link": "https://homesector.bg/products/masa?variant=18"}
    first = {**BASE, "color": "Червен"}
    data, report = generate_favi([first, second], "BG")
    items = ET.fromstring(data).findall("./channel/item")
    ns = {"g": "http://base.google.com/ns/1.0"}
    assert report["items_exported"] == 2
    assert [x.findtext("g:id", namespaces=ns) for x in items] == ["shopifyv17", "shopifyv18"]
    assert [x.findtext("g:item_group_id", namespaces=ns) for x in items] == ["shopifyp12"] * 2
    assert [x.findtext("g:color", namespaces=ns) for x in items] == ["Червен", "Син"]


def test_favi_rejects_ungrouped_variant():
    assert "missing_or_invalid_favi_group_id" in validate({**BASE, "item_group_id": None}, "BG")


def test_shopify_color_and_stock_normalize_to_one_offer_per_variant():
    from feeds.markets_normalize import normalize_market

    product = {
        "id": "gid://shopify/Product/12", "title": "Стол Cleon",
        "handle": "stol-cleon", "status": "ACTIVE", "published_BG": True,
        "descriptionHtml": "Трапезен стол", "vendor": "Atmosphera",
        "featuredImage": {"url": "https://cdn.shopify.com/cleon.jpg"},
        "variantsCount": {"count": 2}, "variants": {"nodes": []},
    }
    for variant_id, color, quantity in ((17, "Кафяв", 5), (18, "Бежов", 0)):
        product["variants"]["nodes"].append({
            "id": f"gid://shopify/ProductVariant/{variant_id}",
            "displayName": f"Стол Cleon - {color}",
            "selectedOptions": [{"name": "Цвят", "value": color}],
            "inventoryQuantity": quantity, "inventoryPolicy": "CONTINUE",
            "price_BG": {"price": {"amount": "99.00", "currencyCode": "EUR"}},
        })
    rows = normalize_market(product, "BG")
    assert len(rows) == 2  # five units in stock do not create five offers
    assert {row["item_group_id"] for row in rows} == {"shopifyp12"}
    assert {row["color"] for row in rows} == {"Кафяв", "Бежов"}
    assert all(row["availability"] == "in_stock" for row in rows)
