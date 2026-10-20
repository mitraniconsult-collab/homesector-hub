"""FAVI BG category coverage and unpublished preview from existing durable journal.

Only map exact, unambiguous Bulgarian leaf names from FAVI's public category
list. All others remain review candidates, never silently assigned.
No external feed is served or submitted.
"""
import json
import os
import re
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
import requests

from .favi_xml import generate_favi
from .feed_ids import is_safe_favi_id, variant_feed_id

FAVI_CATEGORY_LIST = "https://favi.bg/partner-dashboard/category-list"

class CategoryLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.stack.append({"href": dict(attrs).get("href", ""), "text": ""})
    def handle_data(self, data):
        if self.stack:
            self.stack[-1]["text"] += data
    def handle_endtag(self, tag):
        if tag == "a" and self.stack:
            current = self.stack.pop()
            label = " ".join(current["text"].split())
            if " > " in label and len(label) < 240:
                self.links.append(label)

def canon(value):
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()

def leaf(value):
    return canon(str(value).split(">")[-1])

def read_taxonomy():
    result = requests.get(FAVI_CATEGORY_LIST, timeout=40, allow_redirects=False)
    result.raise_for_status()
    parser = CategoryLinks()
    parser.feed(result.text)
    return sorted(set(parser.links))

def audit(mount):
    mount = Path(mount)
    manifest = json.loads((mount / "google-bg/manifest.json").read_text())
    if not manifest.get("finished"):
        raise RuntimeError("Full Google BG journal is required")
    categories = read_taxonomy()
    if len(categories) < 100:
        raise RuntimeError("Public FAVI category list could not be parsed adequately")
    index = defaultdict(set)
    for cat in categories:
        index[leaf(cat)].add(cat)
    historical_path = mount / "favi-historical-id-matches.json"
    historical = {}
    if historical_path.exists():
        historical = {
            e["new_shopify_gid"]: e["legacy_favi_candidate_id"]
            for e in json.loads(historical_path.read_text())
        }
    source_types = Counter()
    stats = Counter()
    rejection = Counter()
    candidates = []
    with (mount / "google-bg/records.jsonl").open(encoding="utf-8") as fh:
        for raw in fh:
            row = json.loads(raw)
            stats["rows"] += 1
            source_type = str(row.get("product_type") or "").strip()
            source_types[source_type or "(missing)"] += 1
            possible = index.get(canon(source_type), set())
            old_id = historical.get(row.get("id"))
            if old_id and not is_safe_favi_id(old_id):
                stats["historic_id_needs_review"] += 1
            if len(possible) == 1:
                stats["unique_exact_leaf_candidate"] += 1
                # No approval evidence: NEVER mark verified automatically.
                if len(candidates) < 100:
                    candidates.append({"shopify_product_type": source_type,
                                       "favi_path": next(iter(possible)),
                                       "status": "candidate_only"})
            elif len(possible) > 1:
                stats["ambiguous_leaf"] += 1
            else:
                stats["not_exactly_mapped"] += 1
    report = {
        "mode": "unpublished_category_audit",
        "catalog_rows": stats["rows"],
        "official_favi_paths": len(categories),
        "historical_id_rows": len(historical),
        "historical_id_with_disallowed_chars": stats["historic_id_needs_review"],
        "unique_exact_leaf_candidates": stats["unique_exact_leaf_candidate"],
        "ambiguous_leaf": stats["ambiguous_leaf"],
        "not_exactly_mapped": stats["not_exactly_mapped"],
        "top_shopify_product_types": source_types.most_common(25),
        "candidate_mapping_samples": candidates[:20],
        "mapping_approved": False,
        "published": False,
    }
    temp = mount / "favi-bg-category-audit.tmp"
    output = mount / "favi-bg-category-audit.json"
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    os.replace(temp, output)
    return report
