"""FAVI-compatible Google RSS XML serializer and validation.

Reference: https://help.favionline.com/en/xml-feed-requirements
FAVI accepts Google format; descriptive localized product_type is mandatory.
"""
from xml.etree import ElementTree as ET
from urllib.parse import urlsplit

G = "http://base.google.com/ns/1.0"
ET.register_namespace("g", G)
REQUIRED = ("id", "title", "description", "link", "image_link", "product_type", "price", "currency")

def validate(row):
    missing = [key for key in REQUIRED if not str(row.get(key) or "").strip()]
    if missing:
        return "missing_" + ",".join(missing)
    if not row["link"].startswith("https://") or not row["image_link"].startswith("https://"):
        return "invalid_https_url"
    if not urlsplit(row["link"]).netloc or not urlsplit(row["image_link"]).netloc:
        return "invalid_url"
    if not row.get("available") and not row.get("continue_selling"):
        return "unavailable"
    return None

def generate_favi(rows):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Homesector"
    ET.SubElement(channel, "link").text = "https://homesector.bg"
    ET.SubElement(channel, "description").text = "Homesector products"
    rejected = {}
    seen = set()
    for row in rows:
        reason = validate(row)
        item_id = str(row.get("id") or "")
        if item_id in seen:
            reason = "duplicate_id"
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        seen.add(item_id)
        item = ET.SubElement(channel, "item")
        for field in ("id", "title", "description", "link", "image_link",
                      "product_type", "brand", "gtin", "mpn", "item_group_id"):
            if row.get(field):
                ET.SubElement(item, f"{{{G}}}{field}").text = str(row[field])
        ET.SubElement(item, f"{{{G}}}price").text = f"{row['price']} {row['currency']}"
        ET.SubElement(item, f"{{{G}}}availability").text = (
            "in_stock" if row.get("available") else "backorder"
        )
        ET.SubElement(item, f"{{{G}}}condition").text = "new"
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True), rejected
