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
# Partial official BG taxonomy snapshot, transcribed from FAVI's public category
# list on 2026-10-20. This is NOT the full live taxonomy or category approval.
VERIFIED_SAMPLE = [
    "градина > градински постройки > перголи",
    "градина > градински постройки > беседки",
    "градина > градински столове",
    "градина > градински маси",
    "градина > градински комплекти",
    "градина > градински люлки",
    "градина > градински пейки",
    "градина > шезлонги",
    "градина > градински текстил > покривала за градински мебели",
    "градина > градински текстил > градински възглавници",
    "градина > чадъри и сенници > градински чадъри",
    "градина > чадъри и сенници > стойки за чадъри",
    "градина > градинарство > цветарници",
    "декорация > вази",
    "декорация > картини",
    "декорация > декоративни купи",
    "декорация > декорация за дома > статуетки",
    "декорация > декорация за детската стая > детски огледала",
    "коридор и антре > огледала",
    "коридор и антре > конзолни маси",
    "коридор и антре > закачалки за антре",
    "коридор и антре > поставки за чадъри",
    "коридор и антре > шкафове за обувки",
    "кухня и трапезария > готвене > тигани",
    "кухня и трапезария > готвене > тенджери",
    "кухня и трапезария > готвене > дъски за рязане",
    "кухня и трапезария > за печене > тави за печене",
    "кухня и трапезария > за печене > форми за печене",
    "мебели > системи за съхранение > гардероби",
    "мебели > системи за съхранение > детски рафтове",
    "мебели > системи за съхранение > рафтове за стена",
    "мебели > системи за съхранение > скринове",
    "мебели > системи за съхранение > стелажи",
    "мебели > системи за съхранение > кутии и органайзери",
    "мебели > столове > бар столове",
    "мебели > столове > трапезни столове",
    "мебели > столове > офис столове",
    "мебели > столове > детски столове и кресла > детски столчета",
    "мебели > шкафове и гардероби > кухненски шкафове",
    "мебели > шкафове и гардероби > детски гардероби",
    "мебели > шкафове и гардероби > витрини",
    "мебели > стойки и закачалки > детски закачалки",
    "обзавеждане за баня > аксесоари за баня > завеси за баня",
    "Коледа > коледни елхи и цветя > коледни елхи",
    "Коледа > коледни венци",
    "Коледа > коледни свещи",
    "Коледа > коледни свещници",
]

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
    taxonomy_live = True
    try:
        categories = read_taxonomy()
        if len(categories) < 100:
            raise RuntimeError("FAVI category page has too few parsed categories")
    except (requests.RequestException, RuntimeError):
        taxonomy_live = False
        categories = VERIFIED_SAMPLE
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
        "official_favi_paths_considered": len(categories),
        "complete_live_taxonomy": taxonomy_live,
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
