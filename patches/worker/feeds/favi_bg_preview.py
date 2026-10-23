"""Create a private FAVI BG XML preview from category-verified mappings.

Maps *standard* Shopify taxonomy paths to known public FAVI BG category paths.
This is NOT an approved FAVI submission and does not modify active feeds.
"""
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from .favi_xml import generate_favi
from .favi_gr_audit import audit_favi_gr
from .feed_ids import is_safe_favi_id, variant_feed_id
from .xml_audit import validate_xml

# Exact Shopify taxonomy -> detailed Bulgarian category PROPOSALS.
# FAVI allows own detailed, localized categories, but platform approval is still required.
# Never infer from product titles, broad parent categories or collections.
CATEGORY_MAP_BG = {
    "Home & Garden > Decor > Seasonal & Holiday Decorations > Holiday Ornaments": "Коледа > коледни орнаменти > коледни играчки за елха",
    "Home & Garden > Decor > Seasonal & Holiday Decorations > Seasonal Village Sets & Accessories": "Коледа > коледна украса > коледни фигурки",
    "Home & Garden > Decor > Throw Pillows": "домашен текстил > текстил за спалня > възглавници и калъфки",
    "Home & Garden > Household Supplies > Storage & Organization > Household Storage Containers": "мебели > системи за съхранение > кутии и органайзери",
    "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Tumblers": "кухня и трапезария > за трапезата > съдове за хранене > чаши > чаши за вода и безалкохолно",
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
    # Exact Shopify taxonomy leaves measured in the 2026-10-23 BG run;
    # destination paths checked against FAVI.bg's current category list.
    "Home & Garden > Linens & Bedding > Bedding > Bed Sheets": "домашен текстил > текстил за спалня > чаршафи",
    "Furniture > Chairs > Kitchen & Dining Room Chairs": "мебели > столове > трапезни столове",
    "Home & Garden > Household Supplies > Laundry Supplies > Laundry Baskets": "обзавеждане за баня > аксесоари за баня > кошове за пране",
    "Furniture > Tables > Accent Tables > Coffee Tables": "дневна > маси за кафе",
    "Furniture > Cabinets & Storage > Dressers": "мебели > шкафове и гардероби > скринове",
    "Home & Garden > Linens & Bedding > Bedding > Blankets": "домашен текстил > текстил за спалня > одеяла",
    "Home & Garden > Lawn & Garden > Outdoor Living > Outdoor Umbrellas & Sunshades > Outdoor Umbrellas": "градина > чадъри и сенници > градински чадъри",
    "Home & Garden > Bathroom Accessories > Bath Mats & Rugs": "обзавеждане за баня > текстил за баня > постелки за баня",
    "Home & Garden > Bathroom Accessories > Soap & Lotion Dispensers": "обзавеждане за баня > аксесоари за баня > дозатори за течен сапун",
    "Furniture > Shelving > Bookcases & Standing Shelves > Modular Bookcases & Shelves": "мебели > системи за съхранение > етажерки за книги",
    "Home & Garden > Decor > Clocks > Wall Clocks": "декорация > часовници",
    "Furniture > Outdoor Furniture > Outdoor Seating > Sunloungers": "градина > шезлонги",
    "Furniture > Outdoor Furniture > Outdoor Seating > Outdoor Chairs > Folding Chairs": "градина > градински столове",
    "Furniture > Chairs > Armchairs, Recliners & Sleeper Chairs > Armchairs": "мебели > мека мебел > фотьойли",
    "Home & Garden > Linens & Bedding > Table Linens > Tablecloths": "домашен текстил > кухненски текстил > покривки",
    "Furniture > Cabinets & Storage > Vanities > Bathroom Vanities > Bathroom Cabinets": "обзавеждане за баня > мебели за баня > шкафове за баня",
    "Home & Garden > Kitchen & Dining > Cookware & Bakeware > Cookware > Skillets & Frying Pans > Frying Pans": "кухня и трапезария > готвене > тигани",
    "Home & Garden > Lighting > Lamps > Floor Lamps": "осветление > лампиони",
    "Home & Garden > Linens & Bedding > Bedding > Quilts & Comforters": "домашен текстил > текстил за спалня > завивки и възглавници",
    "Home & Garden > Lighting > Lamps > Table Lamps": "осветление > настолни лампи",
    "Home & Garden > Bathroom Accessories > Toothbrush Holders": "обзавеждане за баня > аксесоари за баня > поставки за четки за зъби",
    "Furniture > Tables > Kitchen & Dining Room Tables": "мебели > маси > трапезни маси",
    "Furniture > Chairs > Table & Bar Stools > Bar Stools": "мебели > столове > бар столове",
    "Home & Garden > Linens & Bedding > Table Linens > Placemats": "домашен текстил > кухненски текстил > подложки за хранене",
    "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Coffee & Tea Cups": "кухня и трапезария > за трапезата > съдове за хранене > чаши за кафе и чай",
    "Home & Garden > Decor > Coat & Hat Racks": "коридор и антре > закачалки за антре",
    "Furniture > Tables > Accent Tables > End Tables": "дневна > помощни маси",
    "Home & Garden > Kitchen & Dining > Tableware > Serveware > Serving Bowls": "кухня и трапезария > за трапезата > съдове за хранене > купи",
    "Home & Garden > Kitchen & Dining > Kitchen Tools & Utensils > Cutting Boards": "кухня и трапезария > готвене > дъски за рязане",
    "Home & Garden > Linens & Bedding > Towels > Bath Towels & Washcloths > Bath Towels": "обзавеждане за баня > текстил за баня > кърпи за баня",
    "Home & Garden > Household Supplies > Storage & Organization > Clothing & Closet Storage > Hangers": "спалня > закачалки за дрехи",
    "Home & Garden > Linens & Bedding > Bedding > Blankets > Throw Blankets": "домашен текстил > текстил за спалня > одеяла",
    "Furniture > Sofas": "мебели > мека мебел > дивани",
    "Furniture > Tables > Nightstands": "мебели > маси > нощни шкафчета",
    "Home & Garden > Kitchen & Dining > Tableware > Serveware > Serving Platters": "кухня и трапезария > за трапезата > табли за сервиране",
    "Home & Garden > Kitchen & Dining > Kitchen Tools & Utensils > Kitchen Utensil Sets": "кухня и трапезария > кухненски пособия > кухненски прибори",
    "Furniture > Tables > Accent Tables > Console Tables": "коридор и антре > конзолни маси",
    "Furniture > Outdoor Furniture > Outdoor Tables > Side Tables": "градина > балкон и тераса > мебели за тераса > маси за тераса",
    "Home & Garden > Kitchen & Dining > Cookware & Bakeware > Cookware > Stock Pots": "кухня и трапезария > готвене > тенджери",
    "Home & Garden > Bathroom Accessories > Soap Dishes & Holders": "обзавеждане за баня > аксесоари за баня > сапунерки",
    "Furniture > Outdoor Furniture > Outdoor Furniture Sets": "градина > градински комплекти",
    "Furniture > Ottomans": "мебели > мека мебел > табуретки",
    "Home & Garden > Decor > Chair & Sofa Cushion Covers": "домашен текстил > възглавници и калъфки",
    "Home & Garden > Decor > Chair & Sofa Cushions": "домашен текстил > възглавници и калъфки",
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
    migration_xml_audit = validate_xml(migration_xml, "BG", max_issues=0)
    migration_favi_audit = audit_favi_gr(migration_xml)
    if (not migration_xml_audit["passed"] or not migration_favi_audit["passed"]
            or migration_xml_audit["items"] != migration_report["items_exported"]
            or migration_xml_audit["unique_ids"] != migration_xml_audit["items"]):
        raise RuntimeError("FAVI BG migration candidate failed private XML audit")
    migration_path = root / "favi-bg-id-migration-candidate.xml"
    migration_temp = root / "favi-bg-id-migration-candidate.xml.tmp"
    with migration_temp.open("wb") as file:
        file.write(migration_xml)
        file.flush()
        os.fsync(file.fileno())
    os.replace(migration_temp, migration_path)
    candidate_paths = Counter(row["product_type"] for row in prepared + migration_rows)
    report = {
        "status": "unpublished_preview", "market": "BG",
        "source_complete": True, "generated_at": datetime.now(timezone.utc).isoformat(),
        "original_catalog_items": m["items"],
        "xml_items": count, "candidate_category_rows": len(prepared),
        "categories_mapped": len(candidate_paths),
        "categories_mapped_strict": len(per_path),
        "reused_historical_ids": old_ids,
        "new_stable_ids": new_ids,
        "skipped_no_checked_mapping": causes["no_checked_category_mapping"],
        "blocked_legacy_id_migration": causes["legacy_id_requires_migration_review"],
        "blocked_missing_parent_group": causes["missing_shopify_parent_group"],
        "serializer_rejections": xml_report["excluded_reasons"],
        "category_paths_await_favi_approval": True,
        "historical_ids_not_verified_in_favi_panel": True,
        "top_mapped_paths": candidate_paths.most_common(15),
        "top_unmapped_shopify_taxonomy": unmapped_taxonomy.most_common(30),
        "legacy_id_patterns_held": dict(legacy_id_patterns),
        "id_migration_candidate_items": migration_report["items_exported"],
        "id_migration_candidate_rejections": migration_report["excluded_reasons"],
        "id_migration_candidate_sha256": hashlib.sha256(migration_xml).hexdigest(),
        "id_migration_candidate_xml_audit": migration_xml_audit,
        "id_migration_candidate_favi_audit": migration_favi_audit,
        "sha256": hashlib.sha256(xml).hexdigest(),
        "approved_by_favi": False, "published": False,
    }
    output = root / "favi-bg-preview-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report
