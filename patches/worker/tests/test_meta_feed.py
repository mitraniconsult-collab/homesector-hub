from xml.etree import ElementTree as ET
from feeds.meta_xml import generate_meta
from feeds.xml_export import GOOGLE_NS

ROW = {
    "id": "gid://shopify/ProductVariant/42", "title": "Трапезен стол",
    "description": "Удобен стол", "link": "https://homesector.bg/products/stol?variant=42",
    "image_link": "https://cdn.shopify.com/stol.jpg",
    "price": "89.00", "currency": "EUR", "active": True,
    "published": True, "markets": ["BG"],
    "available": True, "continue_selling": False, "brand": "Atmosphera",
}

def test_meta_bg_xml_counts_and_availability():
    xml, report = generate_meta([ROW], "BG")
    root = ET.fromstring(xml)
    items = root.findall("./channel/item")
    assert len(items) == 1
    assert items[0].find("{" + GOOGLE_NS + "}availability").text == "in stock"
    assert report["items_exported"] == 1

def test_meta_unverified_market_translations_are_excluded():
    row = {**ROW, "currency": "RON", "markets": ["RO"],
           "link": "https://homesector.ro/products/stol?variant=42"}
    xml, report = generate_meta([row], "RO")
    assert report["items_exported"] == 0
    assert report["excluded"]["unverified_localized_copy"] == 1
    assert len(ET.fromstring(xml).findall("./channel/item")) == 0

def test_meta_duplicate_ids_are_excluded():
    _, report = generate_meta([ROW, ROW], "BG")
    assert report["items_exported"] == 1
    assert report["excluded"]["duplicate_or_missing_variant_id"] == 1
