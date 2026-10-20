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

def test_favi_backorder_requires_date():
    row = {**BASE, "available": False, "continue_selling": True}
    assert "missing_backorder_availability_date" in validate(row, "BG")
    row["availability_date"] = "2026-11-25T13:00:00+02:00"
    assert "missing_backorder_availability_date" not in validate(row, "BG")

def test_favi_rejects_special_characters_in_ids():
    row = {**BASE, "id": "shopify-v17"}
    assert "invalid_favi_alphanumeric_id" in validate(row, "BG")

def test_favi_duplicate_url_prevents_catalog_merge():
    rows = [BASE, {**BASE, "id": "shopifyv18"}]
    data, report = generate_favi(rows, "BG")
    assert report["items_exported"] == 1
    assert report["excluded_reasons"]["duplicate_or_missing_url"] == 1
