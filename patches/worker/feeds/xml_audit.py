"""Strict XML audit before any feed is made public.

Works on generated RSS 2.0 with Google namespace. Does not send any data.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from .config import MARKETS

G = "{http://base.google.com/ns/1.0}"
REQUIRED = ("id", "title", "description", "link", "image_link", "price", "availability", "condition")

def validate_xml(content, market="BG", max_issues=25):
    if market not in MARKETS:
        raise ValueError("Unsupported market")
    root = ET.fromstring(content)
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
