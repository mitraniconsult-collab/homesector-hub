"""Unpublished multichannel feed preparation. No network calls and no publishing.

Meta uses Google's RSS product fields; FAVI additionally requires category text.
Biano uses its own shop feed format and must be validated against local specs.
"""
from collections import Counter
from xml.etree import ElementTree as ET

from .targets import enabled, targets
from .config import eligible, MARKETS
from .markets_normalize import normalize_market
from .xml_export import generate as generate_google_xml
from .favi_xml import validate as validate_favi, generate_favi

def assess(catalog, country, channel):
    if not enabled(channel, country):
        raise ValueError("Feed target is not configured")
    reasons = Counter()
    rows = []
    seen = set()
    scanned = 0
    for product in catalog:
        scanned += 1
        if product.get("status") != "ACTIVE":
            reasons["inactive"] += 1
            continue
        if not product.get("published_" + country):
            reasons["not_published_in_market"] += 1
            continue
        if not product.get("handle"):
            reasons["missing_handle"] += 1
            continue
        for variant in (product.get("variants") or {}).get("nodes") or []:
            row_product = dict(product)
            row_product["variants"] = {"nodes": [variant]}
            rows_for_variant = normalize_market(row_product, country)
            if not rows_for_variant:
                reasons["missing_price_image_or_currency"] += 1
                continue
            row = rows_for_variant[0]
            if not eligible(row, country):
                reasons["not_eligible"] += 1
                continue
            if not row.get("id") or row["id"] in seen:
                reasons["duplicate_or_missing_variant"] += 1
                continue
            if channel == "favi":
                err = validate_favi(row)
                if err:
                    reasons["favi_" + err] += 1
                    continue
            if channel == "biano":
                # Do not silently output a Google XML file as a Biano feed.
                reasons["biano_serializer_pending"] += 1
                continue
            seen.add(row["id"])
            rows.append(row)
    return {"channel": channel, "market": country, "products_scanned": scanned,
            "eligible_variants": len(rows), "excluded": dict(reasons), "rows": rows}

def unpublished_xml(result):
    channel = result["channel"]
    country = result["market"]
    if channel == "google" or channel == "meta":
        xml = generate_google_xml(result["rows"], country, channel)
    elif channel == "favi":
        xml, rejected = generate_favi(result["rows"])
        if rejected:
            raise RuntimeError("FAVI validation did not match assessment")
    else:
        raise RuntimeError("Biano XML serializer requires format validation")
    ET.fromstring(xml)
    return xml

def target_readiness():
    return [
        {"channel": channel, "market": market,
         "serializer": "draft" if channel in ("google", "meta", "favi") else "pending",
         "localization": "not_validated" if market != "BG" else "base_language",
         "ready_to_publish": False}
        for channel, market in targets()
    ]
