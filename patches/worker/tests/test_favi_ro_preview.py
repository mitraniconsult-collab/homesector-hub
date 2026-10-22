"""RO preview protects localization, grouping, pricing and stock policy."""
from xml.etree import ElementTree as ET

from feeds.favi_ro_preview import create_preview
from feeds.markets_catalog import catalog_query

G = "{http://base.google.com/ns/1.0}"
PID = "gid://shopify/Product/12"


def sample():
    product = {
        "id": PID, "title": "Стол Cleon", "handle": "stol-cleon",
        "status": "ACTIVE", "published_RO": True,
        "verified_market_url_RO": "https://homesector.ro/products/scaun-cleon",
        "descriptionHtml": "Стол", "vendor": "Atmosphera",
        "featuredImage": {"url": "https://cdn.shopify.com/cleon.jpg"},
        "variantsCount": {"count": 2}, "variants": {"nodes": []},
    }
    for vid, color, qty in ((17, "Кафяв", 0), (18, "Бежов", 5)):
        product["variants"]["nodes"].append({
            "id": f"gid://shopify/ProductVariant/{vid}",
            "selectedOptions": [{"name": "Цвят", "value": color}],
            "inventoryQuantity": qty, "inventoryPolicy": "CONTINUE",
            "price_RO": {"price": {"amount": "470.00", "currencyCode": "RON"}},
        })
    translated = {PID: {"RO": [
        {"key": "title", "value": "Scaun Cleon"},
        {"key": "body_html", "value": "<p>Scaun cu cadru din lemn.</p>"},
    ]}}
    variants = {
        "gid://shopify/ProductVariant/17": [{"key": "option1", "value": "Maro"}],
        "gid://shopify/ProductVariant/18": [{"key": "option1", "value": "Bej"}],
    }
    categories = {PID: {"market": "RO", "path": "Scaune de sufragerie", "verified": True}}
    return product, translated, variants, categories


def test_romanian_variants_share_group_have_unique_links_and_keep_continue_selling():
    product, translated, variants, categories = sample()
    xml, report = create_preview([product], categories, {PID}, translated, variants)
    items = ET.fromstring(xml).findall("./channel/item")
    assert report["xml_items"] == 2
    assert {x.findtext(G + "item_group_id") for x in items} == {"shopifyp12"}
    assert {x.findtext(G + "color") for x in items} == {"Maro", "Bej"}
    assert len({x.findtext("link") for x in items}) == 2
    assert all(x.findtext("link").startswith("https://homesector.ro/products/scaun-cleon?variant=") for x in items)
    assert all(x.findtext(G + "availability") == "in_stock" for x in items)
    assert all(x.findtext(G + "price") == "470.00 RON" for x in items)


def test_swapped_color_and_missing_local_copy_or_url_are_rejected():
    product, translated, variants, categories = sample()
    variants["gid://shopify/ProductVariant/17"][0]["value"] = "Bej"
    _, report = create_preview([product], categories, {PID}, translated, variants)
    assert report["preflight_exclusions"]["unverified_romanian_variant_color"] == 1
    _, report = create_preview([product], categories, set(), translated, variants)
    assert report["xml_items"] == 0
    assert report["preflight_exclusions"]["unverified_market_url"] == 2
    _, report = create_preview([product], categories, {PID}, {}, variants)
    assert report["preflight_exclusions"]["unverified_localized_copy"] == 2


def test_ro_source_query_uses_romanian_context_and_includes_taxonomy():
    query = catalog_query(ro_only=True)
    assert "country: RO" in query
    assert "country: GR" not in query
    assert "category { id fullName }" in query
    assert "products(first: 25" in query
