"""FAVI Google RSS feed with strict destination-specific fail-closed checks.

No public publishing. Require accepted local-language category and verified
market links. Existing FAVI IDs must be reconciled before any replacement.
"""
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from .config import MARKETS
from .feed_ids import is_safe_favi_id
from .channel_quality import check_product

G = "http://base.google.com/ns/1.0"
ET.register_namespace("g", G)

def validate(row, market):
    issues = check_product(row, market, "favi")
    if not is_safe_favi_id(row.get("id")):
        issues.append("invalid_favi_alphanumeric_id")
    if row.get("item_group_id") and not is_safe_favi_id(row["item_group_id"]):
        issues.append("invalid_favi_group_id")
    if not row.get("available"):
        date = str(row.get("availability_date") or "")
        try:
            valid = bool(date and datetime.fromisoformat(date.replace("Z", "+00:00")).tzinfo)
        except ValueError:
            valid = False
        if not valid:
            issues.append("missing_backorder_availability_date")
    if row.get("link"):
        parsed = urlsplit(str(row["link"]))
        if parsed.fragment or any(c.isspace() for c in str(row["link"])):
            issues.append("invalid_product_url")
    return sorted(set(issues))

def _g(item, field, value):
    if value is not None and str(value).strip():
        ET.SubElement(item, "{" + G + "}" + field).text = str(value)

def generate_favi(rows, market="BG"):
    # Target is restricted by channel_quality / targets.py.
    if market not in MARKETS:
        raise ValueError("Unsupported market")
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Homesector FAVI " + market
    ET.SubElement(channel, "link").text = "https://" + MARKETS[market]["domain"]
    ET.SubElement(channel, "description").text = "Homesector feed"
    reasons, seen_ids, seen_urls = Counter(), set(), set()
    count = 0
    for row in rows:
        issues = validate(row, market)
        item_id = str(row.get("id") or "")
        link = str(row.get("link") or "")
        if not item_id or item_id in seen_ids:
            issues.append("duplicate_or_missing_id")
        if not link or link in seen_urls:
            issues.append("duplicate_or_missing_url")
        if issues:
            reasons.update(set(issues))
            continue
        seen_ids.add(item_id)
        seen_urls.add(link)
        item = ET.SubElement(channel, "item")
        for field in ("id", "title", "description", "link", "image_link",
                      "product_type", "brand", "gtin", "mpn", "item_group_id"):
            _g(item, field, row.get(field))
        _g(item, "price", f"{row['price']} {row['currency']}")
        _g(item, "availability", "in_stock" if row.get("available") else "backorder")
        if not row.get("available"):
            _g(item, "availability_date", row["availability_date"])
        _g(item, "condition", "new")
        count += 1
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True), {
        "market": market, "items_exported": count,
        "excluded_reasons": dict(sorted(reasons.items())),
        "published": False, "validated_by_favi": False,
    }
