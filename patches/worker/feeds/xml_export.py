"""XML serializers for feed export. Input is a list of normalized Shopify variants."""
from xml.etree import ElementTree as ET
from .config import MARKETS, CHANNELS, eligible

GOOGLE_NS = "http://base.google.com/ns/1.0"
ET.register_namespace("g", GOOGLE_NS)


def add(parent, name, value):
    if value is not None and str(value).strip():
        ET.SubElement(parent, name).text = str(value)


def generate(products, market, channel):
    if market not in MARKETS or channel not in CHANNELS:
        raise ValueError("Unsupported feed configuration")
    root = ET.Element("rss", version="2.0")
    node = ET.SubElement(root, "channel")
    add(node, "title", "Homesector " + market + " " + channel)
    add(node, "link", "https://" + MARKETS[market]["domain"])
    add(node, "description", "Homesector catalog")
    for p in products:
        if not eligible(p, market):
            continue
        item = ET.SubElement(node, "item")
        for field in ("id", "title", "description", "link", "image_link", "brand", "gtin", "mpn", "product_type"):
            add(item, "{" + GOOGLE_NS + "}" + field, p.get(field))
        add(item, "{" + GOOGLE_NS + "}price", str(p["price"]) + " " + p["currency"])
        add(item, "{" + GOOGLE_NS + "}availability", "in_stock" if p.get("available") else "backorder")
        if not p.get("available"):
            add(item, "{" + GOOGLE_NS + "}availability_date", p.get("availability_date"))
        add(item, "{" + GOOGLE_NS + "}condition", "new")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
