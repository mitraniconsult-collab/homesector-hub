"""Strict XML audit before any feed is made public.

Works on generated RSS 2.0 with Google namespace. Does not send any data.
"""
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from datetime import datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from .config import MARKETS

G = "{http://base.google.com/ns/1.0}"
REQUIRED = ("id", "title", "description", "link", "image_link", "price", "availability", "condition")

def validate_xml(content, market="BG", max_issues=25):
    if market not in MARKETS:
        raise ValueError("Unsupported market")
    root = content if isinstance(content, ET.Element) else ET.fromstring(content)
    if root.tag != "rss":
        raise ValueError("Not an RSS feed")
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS channel missing")
    items = channel.findall("item")
    counts, seen, examples = Counter(), set(), []
    currency = MARKETS[market]["currency"]
    domain = MARKETS[market]["domain"]
    for item in items:
        data = {key: (item.findtext(G + key) or "").strip() for key in REQUIRED}
        issues = set()
        for key in REQUIRED:
            if not data[key]:
                issues.add("missing_" + key)
        item_id = data["id"]
        if item_id in seen or not item_id:
            issues.add("duplicate_or_blank_id")
        seen.add(item_id)
        if data["link"]:
            u = urlsplit(data["link"])
            if u.scheme != "https" or u.hostname != domain:
                issues.add("wrong_market_link")
        if data["image_link"]:
            if urlsplit(data["image_link"]).scheme != "https":
                issues.add("invalid_image_link")
        if data["price"]:
            try:
                amount, ccy = data["price"].rsplit(" ", 1)
                if ccy != currency or Decimal(amount) <= 0:
                    issues.add("invalid_amount_or_currency")
            except (ValueError, InvalidOperation):
                issues.add("invalid_amount_or_currency")
        if data["availability"] not in ("in_stock", "out_of_stock", "backorder", "preorder"):
            issues.add("invalid_google_availability")
        if data["availability"] in ("backorder", "preorder"):
            date = (item.findtext(G + "availability_date") or "").strip()
            try:
                parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                if parsed_date.tzinfo is None:
                    issues.add("invalid_backorder_availability_date")
            except ValueError:
                issues.add("invalid_backorder_availability_date")
        if data["condition"] not in ("new", "used", "refurbished"):
            issues.add("invalid_condition")
        if issues and len(examples) < max_issues:
            examples.append({"id": item_id, "issues": sorted(issues)})
        counts.update(issues)
    return {
        "market": market, "items": len(items), "unique_ids": len(seen),
        "issues": dict(sorted(counts.items())), "examples": examples,
        "passed": bool(items) and not counts, "submitted": False
    }


def validated_preview(content, market="BG"):
    """Separate private candidate; preserve every retained ID and source XML.

    Invalid rows are counted explicitly. This does not mark the destination as
    having accepted a feed, and it must never silently replace the full export.
    """
    source = ET.fromstring(content)
    # Validate structure before constructing an output (including empty feeds).
    validate_xml(source, market)
    output = deepcopy(source)
    channel = output.find("channel")
    seen, reasons, excluded = set(), Counter(), 0
    for item in list(channel.findall("item")):
        single = ET.Element("rss", version="2.0")
        ET.SubElement(single, "channel").append(item)
        audit = validate_xml(single, market, max_issues=0)
        issues = set(audit["issues"])
        item_id = (item.findtext(G + "id") or "").strip()
        if item_id in seen:
            issues.add("duplicate_or_blank_id")
        if issues:
            channel.remove(item)
            reasons.update(issues)
            excluded += 1
        else:
            seen.add(item_id)
    xml = ET.tostring(output, encoding="utf-8", xml_declaration=True)
    final = validate_xml(xml, market, max_issues=0)
    return xml, {"items": final["items"], "excluded_rows": excluded,
                 "issues": dict(sorted(reasons.items())),
                 "quality_passed": final["passed"], "published": False,
                 "destination_accepted": False}
