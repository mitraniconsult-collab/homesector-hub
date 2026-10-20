"""Meta Catalog RSS export prototype, held behind strict per-market preflight.
Do not publish externally before Meta Commerce Manager validation.
"""
from collections import Counter
from xml.etree import ElementTree as ET
from .availability import feed_availability
from .config import MARKETS
from .channel_quality import check_product
from .xml_export import GOOGLE_NS

ET.register_namespace("g", GOOGLE_NS)

def _add(item, field, value):
    if value is not None and str(value).strip():
        ET.SubElement(item, "{" + GOOGLE_NS + "}" + field).text = str(value)

def generate_meta(rows, market):
    if market not in MARKETS:
        raise ValueError("Unsupported market")
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Homesector Meta " + market
    ET.SubElement(channel, "link").text = "https://" + MARKETS[market]["domain"]
    ET.SubElement(channel, "description").text = "Home and living products"
    reasons = Counter()
    seen = set()
    accepted = 0
    for row in rows:
        problems = check_product(row, market, "meta")
        key = str(row.get("id") or "")
        if not key or key in seen:
            problems.append("duplicate_or_missing_variant_id")
        if problems:
            reasons.update(set(problems))
            continue
        seen.add(key)
        item = ET.SubElement(channel, "item")
        for field in ("id", "title", "description", "link", "image_link",
                      "brand", "gtin", "mpn", "product_type", "item_group_id"):
            _add(item, field, row.get(field))
        _add(item, "price", str(row["price"]) + " " + row["currency"])
        _add(item, "availability", "in stock" if feed_availability(row) == "in_stock" else "available for order")
        _add(item, "condition", "new")
        accepted += 1
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True), {
        "market": market, "items_exported": accepted, "excluded": dict(reasons),
        "published": False, "platform_accepted": False,
    }
