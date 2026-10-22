"""Create a private FAVI BG XML preview from category-verified mappings.

Maps *standard* Shopify taxonomy paths to known public FAVI BG category paths.
This is NOT an approved FAVI submission and does not modify active feeds.
"""
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from .favi_xml import generate_favi
from .feed_ids import is_safe_favi_id, variant_feed_id

# Exact Shopify taxonomy -> detailed Bulgarian category PROPOSALS.
# FAVI allows own detailed, localized categories, but platform approval is still required.
# Never infer from product titles, broad parent categories or collections.
CATEGORY_MAP_BG = {
    "Home & Garden > Decor > Seasonal & Holiday Decorations > Holiday Ornaments": "Коледа > Коледна украса > Играчки за елха",
    "Home & Garden > Decor > Seasonal & Holiday Decorations > Seasonal Village Sets & Accessories": "Коледа > Коледна украса > Коледни селца и аксесоари",
    "Home & Garden > Decor > Throw Pillows": "Домашен текстил > Декоративни възглавници",
    "Home & Garden > Decor > Artificial Flora > Artificial Trees": "Декорация > Изкуствени растения > Изкуствени дървета",
    "Home & Garden > Household Supplies > Storage & Organization > Household Storage Containers": "Организация на дома > Кутии за съхранение",
    "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Tumblers": "Кухня и трапезария > Чаши > Чаши за вода",
    "Home & Garden > Kitchen & Dining > Tableware > Dinnerware > Plates": "кухня и трапезария > за трапезата > съдове за хранене > чинии",
    "Home & Garden > Kitchen & Dining > Tableware > Dinnerware > Bowls": "кухня и трапезария > за трапезата > съдове за хранене > купи",
    "Home & Garden > Kitchen & Dining > Food Storage > Food Storage Containers": "кухня и трапезария > съхранение на храна > контейнери за храна",
    "Home & Garden > Kitchen & Dining > Tableware > Serveware > Serving Trays": "кухня и трапезария > за трапезата > табли за сервиране",
    "Home & Garden > Lighting > Light Ropes & Strings > String Lights": "осветление > декоративно осветление",
    "Home & Garden > Decor > Figurines": "декорация > декорация за дома > статуетки",
    "Home & Garden > Decor > Vases": "декорация > вази",
    "Home & Garden > Decor > Home Fragrances > Candles": "декорация > свещници и свещи > свещи",
    "Home & Garden > Decor > Picture Frames": "декорация > рамки за снимки",
    "Home & Garden > Decor > Rugs": "домашен текстил > килими",
    "Home & Garden > Decor > Window Treatments > Curtains & Drapes > Curtains": "домашен текстил > завеси",
    "Furniture > Outdoor Furniture > Outdoor Seating > Outdoor Chairs": "градина > градински столове",
    "Furniture > Outdoor Furniture > Outdoor Tables > Dining Tables": "градина > градински маси",
    "Home & Garden > Lighting > Lamps > Bedside Lamps": "осветление > настолни лампи",
    "Home & Garden > Decor > Mirrors": "декорация > огледала",
    "Home & Garden > Decor > Home Fragrances > Reed Diffusers": "декорация > свещници и свещи > ароматизатори за стая",
    "Home & Garden > Decor > Artwork > Posters, Prints, & Visual Artwork > Visual Artwork": "декорация > картини",
}

def handle_from_link(link):
    parts = urlsplit(str(link)).path.split("/")
    return parts[2] if len(parts) == 3 and parts[1] == "products" else None

def create_preview(mount, source_folder=None):
    root = Path(mount)
    source_folder = Path(source_folder) if source_folder is not None else root / "google-bg"
    m = json.loads((source_folder / "manifest.json").read_text())
    c = json.loads((root / "favi-shopify-categories/manifest.json").read_text())
    if not m["finished"] or not c["finished"]:
        raise RuntimeError("Completed journals required for FAVI preview")
    cat_by_handle = {}
    with (root / "favi-shopify-categories/products.jsonl").open(encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            if p.get("handle"):
                cat_by_handle[p["handle"]] = p
    historic = {}
    known_legacy = set()
    history_path = root / "favi-historical-id-matches.json"
    if history_path.exists():
        for match in json.loads(history_path.read_text()):
            gid, oldid = match["new_shopify_gid"], match["legacy_favi_candidate_id"]
            known_legacy.add(gid)
            if is_safe_favi_id(oldid):
                historic[gid] = oldid
    prepared, migration_rows, causes, per_path = [], [], Counter(), Counter()
    unmapped_taxonomy = Counter()
    legacy_id_patterns = Counter()
    new_ids, old_ids = 0, 0
    records_path = source_folder / "availability-corrected-records.jsonl"
    if not records_path.exists():
        records_path = source_folder / "records.jsonl"
    with records_path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            handle = handle_from_link(row.get("link"))
            source = cat_by_handle.get(handle, {})
            taxonomy = str(source.get("category_name") or "")
            favi_category = CATEGORY_MAP_BG.get(taxonomy)
            if not favi_category:
                causes["no_checked_category_mapping"] += 1
                unmapped_taxonomy[taxonomy or "(missing)"] += 1
                continue
            if not row.get("item_group_id"):
                causes["missing_shopify_parent_group"] += 1
                continue
            if row.get("id") in historic:
                row["id"] = historic[row["id"]]
                old_ids += 1
            elif row.get("id") in known_legacy:
                # Never silently change IDs for products in the active legacy
                # XML. These require explicit FAVI migration approval.
                causes["legacy_id_requires_migration_review"] += 1
                legacy_id_patterns["punctuated"] += 1
                migration_row = dict(row)
                migration_row["id"] = variant_feed_id(row["id"])
                migration_row["product_type"] = favi_category
                migration_row["category_verified_for_market"] = True
                migration_rows.append(migration_row)
                continue
            else:
                row["id"] = variant_feed_id(row["id"])
                new_ids += 1
            row["product_type"] = favi_category
            row["category_verified_for_market"] = True
            prepared.append(row)
            per_path[favi_category] += 1
    xml, xml_report = generate_favi(prepared, "BG")
    count = len(ET.fromstring(xml).findall("./channel/item"))
    if count != xml_report["items_exported"]:
        raise RuntimeError("FAVI preview XML item count mismatch")
    destination = root / "favi-bg-unpublished.xml"
    temp = root / "favi-bg-unpublished.xml.tmp"
    with temp.open("wb") as file:
        file.write(xml)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, destination)
    # A separate private candidate quantifies the proposed ID migration. It
    # cannot replace the legacy feed without an explicit destination decision.
    migration_xml, migration_report = generate_favi(prepared + migration_rows, "BG")
    migration_path = root / "favi-bg-id-migration-candidate.xml"
    migration_temp = root / "favi-bg-id-migration-candidate.xml.tmp"
    with migration_temp.open("wb") as file:
        file.write(migration_xml)
        file.flush()
        os.fsync(file.fileno())
    os.replace(migration_temp, migration_path)
    report = {
        "status": "unpublished_preview", "original_catalog_items": m["items"],
        "xml_items": count, "candidate_category_rows": len(prepared),
        "categories_mapped": len(per_path),
        "reused_historical_ids": old_ids,
        "new_stable_ids": new_ids,
        "skipped_no_checked_mapping": causes["no_checked_category_mapping"],
        "blocked_legacy_id_migration": causes["legacy_id_requires_migration_review"],
        "blocked_missing_parent_group": causes["missing_shopify_parent_group"],
        "serializer_rejections": xml_report["excluded_reasons"],
        "category_paths_await_favi_approval": True,
        "historical_ids_not_verified_in_favi_panel": True,
        "top_mapped_paths": per_path.most_common(15),
        "top_unmapped_shopify_taxonomy": unmapped_taxonomy.most_common(30),
        "legacy_id_patterns_held": dict(legacy_id_patterns),
        "id_migration_candidate_items": migration_report["items_exported"],
        "id_migration_candidate_rejections": migration_report["excluded_reasons"],
        "id_migration_candidate_sha256": hashlib.sha256(migration_xml).hexdigest(),
        "sha256": hashlib.sha256(xml).hexdigest(),
        "approved_by_favi": False, "published": False,
    }
    output = root / "favi-bg-preview-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report
