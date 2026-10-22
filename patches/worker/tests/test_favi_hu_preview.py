"""HU preview requires HUF, local copy, exact category and distinct variants."""
from xml.etree import ElementTree as ET

from feeds.favi_hu_preview import create_preview
from feeds.favi_hu_taxonomy import categories_for_products
from feeds.markets_catalog import catalog_query

G = "{http://base.google.com/ns/1.0}"
PID = "gid://shopify/Product/12"


def sample():
    product = {
        "id": PID, "title": "Стол Cleon", "handle": "stol-cleon",
        "status": "ACTIVE", "published_HU": True,
        "verified_market_url_HU": "https://homesector.hu/products/cleon-szek",
        "descriptionHtml": "Стол", "vendor": "Atmosphera",
        "featuredImage": {"url": "https://cdn.shopify.com/cleon.jpg"},
        "variantsCount": {"count": 2}, "variants": {"nodes": []},
    }
    for vid, color, qty in ((17, "Кафяв", 0), (18, "Бежов", 5)):
        product["variants"]["nodes"].append({
            "id": f"gid://shopify/ProductVariant/{vid}",
            "selectedOptions": [{"name": "Цвят", "value": color}],
            "inventoryQuantity": qty, "inventoryPolicy": "CONTINUE",
            "price_HU": {"price": {"amount": "49900.00", "currencyCode": "HUF"}},
        })
    translated = {PID: {"HU": [
        {"key": "title", "value": "Cleon szék"},
        {"key": "body_html", "value": "<p>Fa vázas szék.</p>"},
    ]}}
    variants = {
        "gid://shopify/ProductVariant/17": [{"key": "option1", "value": "Barna"}],
        "gid://shopify/ProductVariant/18": [{"key": "option1", "value": "Bézs"}],
    }
    category = {PID: {"market": "HU", "verified": True,
                      "path": "bútorok > székek > étkezőszékek"}}
    return product, translated, variants, category


def test_hu_variants_share_group_have_unique_links_and_keep_continue_selling():
    product, translated, variants, category = sample()
    xml, report = create_preview([product], category, {PID}, translated, variants)
    items = ET.fromstring(xml).findall("./channel/item")
    assert report["xml_items"] == 2
    assert {x.findtext(G + "item_group_id") for x in items} == {"shopifyp12"}
    assert {x.findtext(G + "color") for x in items} == {"Barna", "Bézs"}
    assert len({x.findtext("link") for x in items}) == 2
    assert all(x.findtext("link").startswith(
        "https://homesector.hu/products/cleon-szek?variant=") for x in items)
    assert all(x.findtext(G + "availability") == "in_stock" for x in items)
    assert all(x.findtext(G + "price") == "49900.00 HUF" for x in items)


def test_hu_missing_localization_wrong_currency_and_swapped_color_fail_closed():
    product, translated, variants, category = sample()
    variants["gid://shopify/ProductVariant/17"][0]["value"] = "Bézs"
    _, report = create_preview([product], category, {PID}, translated, variants)
    assert report["preflight_exclusions"]["unverified_hungarian_variant_color"] == 1
    _, report = create_preview([product], category, set(), translated, variants)
    assert report["xml_items"] == 0
    product["variants"]["nodes"][0]["price_HU"]["price"]["currencyCode"] = "EUR"
    _, report = create_preview([product], category, {PID}, translated, variants)
    assert report["xml_items"] == 1
    _, report = create_preview([product], category, {PID}, {}, variants)
    assert report["xml_items"] == 0


def test_hu_query_and_observed_categories():
    query = catalog_query(hu_only=True)
    assert "country: HU" in query
    assert "country: RO" not in query
    assert "category { id fullName }" in query
    selected = categories_for_products([
        {"id": "p1", "category": {"id": "gid://shopify/TaxonomyCategory/fr-24-1-1"}},
        {"id": "p2", "category": {"id": "gid://shopify/TaxonomyCategory/hg-11-10-4-3"}},
    ])
    assert selected["p1"]["path"] == "bútorok > asztalok > dohányzóasztalok"
    assert "p2" not in selected
