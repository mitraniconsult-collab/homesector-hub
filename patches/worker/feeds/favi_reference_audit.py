"""Read-only comparison of legacy Feedhub RSS with durable Shopify feed.

Writes only private staging diagnostics. Does not publish or modify either feed.
"""
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlunsplit
from xml.etree import ElementTree as ET
import requests

G = "{http://base.google.com/ns/1.0}"
LIMIT = 250 * 1024 * 1024

def _key(url):
    p = urlsplit(str(url or ""))
    if not p.path.startswith("/products/"):
        return None
    variant = parse_qs(p.query).get("variant", [])
    return (p.path.rstrip("/").lower(), variant[0] if variant else "")

def _fields(item):
    return {
        "id": item.findtext(G + "id") or item.findtext("id") or "",
        "link": item.findtext(G + "link") or item.findtext("link") or "",
        "product_type": item.findtext(G + "product_type") or item.findtext("product_type") or "",
        "price": item.findtext(G + "price") or item.findtext("price") or "",
    }

def compare(url, mount):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "feedhub-storage.onecommerce.io" or not parsed.path.startswith("/do/data_feed/google_feed/") or not parsed.path.endswith(".xml"):
        raise ValueError("Legacy feed URL is not an approved Feedhub XML path")
    mount = Path(mount)
    generated = mount / "google-bg" / "records.jsonl"
    if not generated.is_file():
        raise RuntimeError("Complete durable Shopify journal required")
    canonical = {}
    with generated.open(encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            key = _key(item.get("link"))
            if key:
                canonical[key] = str(item.get("id", ""))
    count, matched, no_id, empty_category, duplicate_id = 0, 0, 0, 0, 0
    legacy_ids, examples, matches = set(), [], []
    with tempfile.TemporaryFile() as blob:
        with requests.get(url, stream=True, timeout=(15, 60), allow_redirects=False) as res:
            res.raise_for_status()
            size = 0
            for chunk in res.iter_content(65536):
                size += len(chunk)
                if size > LIMIT:
                    raise RuntimeError("Feedhub reference exceeds size limit")
                blob.write(chunk)
        blob.seek(0)
        for _, element in ET.iterparse(blob, events=("end",)):
            if element.tag != "item":
                continue
            count += 1
            item = _fields(element)
            if not item["id"]:
                no_id += 1
            elif item["id"] in legacy_ids:
                duplicate_id += 1
            legacy_ids.add(item["id"])
            if not item["product_type"]:
                empty_category += 1
            key = _key(item["link"])
            if key and key in canonical:
                matched += 1
                matches.append({"new_shopify_gid": canonical[key], "legacy_favi_candidate_id": item["id"]})
            if len(examples) < 4:
                examples.append({"id_pattern": ("numeric" if item["id"].isdigit() else "alphanumeric" if item["id"].isalnum() else "punctuated"), "category_present": bool(item["product_type"]), "currency": item["price"].split()[-1] if item["price"] else ""})
            element.clear()
    report = {"legacy_items": count, "matched_by_product_variant_url": matched,
              "missing_id": no_id, "duplicate_id": duplicate_id,
              "missing_category": empty_category, "new_journal_ids": len(canonical),
              "sample_patterns": examples, "published": False}
    tmp = mount / "favi-reference-report.tmp"
    dest = mount / "favi-reference-report.json"
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, dest)
    match_tmp = mount / "favi-historical-id-matches.tmp"
    match_dest = mount / "favi-historical-id-matches.json"
    match_tmp.write_text(json.dumps(matches, ensure_ascii=False), encoding="utf-8")
    os.replace(match_tmp, match_dest)
    return report
