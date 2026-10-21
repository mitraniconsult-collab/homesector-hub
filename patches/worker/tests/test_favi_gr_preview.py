"""Greek FAVI candidate: real locale, market, color and URL gates."""
from xml.etree import ElementTree as ET
from feeds.favi_gr_preview import create_preview

G = "{http://base.google.com/ns/1.0}"
PRODUCT_ID = "gid://shopify/Product/12"


def sample():
    product = {
        "id": PRODUCT_ID, "title": "Трапезен стол Cleon",
        "handle": "stol-cleon", "status": "ACTIVE", "published_GR": True,
        "descriptionHtml": "Трапезен стол", "vendor": "Atmosphera",
        "featuredImage": {"url": "https://cdn.shopify.com/cleon.jpg"},
        "variantsCount": {"count": 2}, "variants": {"nodes": []},
    }
    for vid, color, qty in ((17, "Кафяв", 0), (18, "Бежов", 5)):
        product["variants"]["nodes"].append({
            "id": f"gid://shopify/ProductVariant/{vid}",
            "displayName": f"Стол Cleon - {color}",
            "selectedOptions": [{"name": "Цвят", "value": color}],
            "inventoryQuantity": qty, "inventoryPolicy": "CONTINUE",
            "price_GR": {"price": {"amount": "99.00", "currencyCode": "EUR"}},
        })
    translated = {PRODUCT_ID: {"GR": [
        {"key": "title", "value": "Καρέκλα τραπεζαρίας Cleon"},
        {"key": "body_html", "value": "<p>Καρέκλα με ξύλινο σκελετό.</p>"},
    ]}}
    colors = {
        "gid://shopify/ProductVariant/17": [{"key": "option1", "value": "Καφέ"}],
        "gid://shopify/ProductVariant/18": [{"key": "option1", "value": "Μπεζ"}],
    }
    category = {PRODUCT_ID: {
        "market": "GR", "path": "Έπιπλα > Καρέκλες τραπεζαρίας",
        "verified": True,
    }}
    return product, translated, colors, category


def test_greek_colors_share_a_parent_and_keep_zero_stock_continue():
    p, t, v, c = sample()
    xml, report = create_preview(
        [p], c, {PRODUCT_ID}, translated_map=t,
        translated_variant_map=v)
    items = ET.fromstring(xml).findall("./channel/item")
    assert report["xml_items"] == 2
    assert len({x.findtext(G + "id") for x in items}) == 2
    assert {x.findtext(G + "item_group_id") for x in items} == {"shopifyp12"}
    assert {x.findtext(G + "color") for x in items} == {"Καφέ", "Μπεζ"}
    assert all(x.findtext(G + "availability") == "in_stock" for x in items)
    assert all(x.findtext(G + "price") == "99.00 EUR" for x in items)
    assert all(x.findtext(G + "link").startswith("https://homesector.gr/") for x in items)


def test_swapped_greek_colors_are_held():
    p, t, v, c = sample()
    v["gid://shopify/ProductVariant/17"][0]["value"] = "Μπεζ"
    v["gid://shopify/ProductVariant/18"][0]["value"] = "Καφέ"
    _, report = create_preview(
        [p], c, {PRODUCT_ID}, translated_map=t,
        translated_variant_map=v)
    assert report["xml_items"] == 0
    assert report["preflight_exclusions"]["unverified_greek_variant_color"] == 2


def test_missing_verified_link_or_category_blocks_greek_offer():
    p, t, v, c = sample()
    _, report = create_preview([p], c, set(), translated_map=t,
                               translated_variant_map=v)
    assert report["preflight_exclusions"]["unverified_market_url"] == 2
    _, report = create_preview([p], {}, {PRODUCT_ID}, translated_map=t,
                               translated_variant_map=v)
    assert report["preflight_exclusions"]["unverified_favi_category"] == 2
