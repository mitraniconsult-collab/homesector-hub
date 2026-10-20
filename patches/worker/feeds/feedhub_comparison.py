"""Compare two real BG RSS snapshots and retain legacy offer identifiers."""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlsplit, urlunsplit, urlencode
from xml.etree import ElementTree as ET

G = "{http://base.google.com/ns/1.0}"
FIELDS = ("id", "link", "title", "price", "availability", "image_link",
          "product_type", "google_product_category")


def read_rows(content):
    root = ET.fromstring(content)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Expected Google RSS feed")
    return [{field: (item.findtext(G + field) or item.findtext(field) or "").strip()
             for field in FIELDS} for item in root.findall("./channel/item")]


def match_key(row):
    link = urlsplit(row["link"])
    host = (link.hostname or "").removeprefix("www.")
    variant = parse_qs(link.query).get("variant", [""])[0]
    if variant:
        return (host, "variant", variant)
    if link.path.startswith("/products/"):
        return (host, "path", link.path.rstrip("/"))
    return (host, "id", row["id"])


def _index(rows):
    index = defaultdict(list)
    for position, row in enumerate(rows):
        index[match_key(row)].append(position)
    return index


def reconcile_ids(legacy, candidate):
    """Use an exact legacy ID only for an unambiguous same-variant match."""
    old_rows, new_rows = read_rows(legacy), read_rows(candidate)
    old_index, new_index = _index(old_rows), _index(new_rows)
    root = ET.fromstring(candidate)
    items = root.findall("./channel/item")
    preserved, unmatched, ambiguous = 0, 0, 0
    for index, row in enumerate(new_rows):
        key = match_key(row)
        matches = old_index.get(key, [])
        if not matches:
            unmatched += 1
            continue
        if len(matches) != 1 or len(new_index[key]) != 1:
            ambiguous += 1
            continue
        historic = old_rows[matches[0]]["id"]
        if not historic:
            raise ValueError("Matched legacy product has no ID")
        item_id = items[index].find(G + "id")
        if item_id is None:
            raise ValueError("Candidate is missing Google ID field")
        item_id.text = historic
        preserved += 1
    result = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    ids = [row["id"] for row in read_rows(result)]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Reconciled feed has blank or duplicate IDs")
    return result, {"historical_ids_preserved": preserved,
                    "new_unmatched_items": unmatched,
                    "ambiguous_matches": ambiguous}


def _value(field, value):
    if field == "link":
        link = urlsplit(value)
        variant = parse_qs(link.query).get("variant", [])
        return urlunsplit((link.scheme, (link.hostname or "").removeprefix("www."),
                           link.path.rstrip("/"), urlencode({"variant": variant[0]}) if variant else "", ""))
    if field == "availability":
        return value.lower().replace(" ", "_")
    if field == "price":
        try:
            amount, currency = value.rsplit(" ", 1)
            return Decimal(amount), currency.upper()
        except (ValueError, InvalidOperation):
            return value
    return value


def compare_snapshots(legacy, candidate, sample_limit=30):
    old, new = read_rows(legacy), read_rows(candidate)
    old_index, new_index = _index(old), _index(new)
    matched, differences, samples = 0, Counter(), []
    matched_old, matched_new = set(), set()
    for key in old_index.keys() & new_index.keys():
        if len(old_index[key]) != 1 or len(new_index[key]) != 1:
            continue
        old_pos, new_pos = old_index[key][0], new_index[key][0]
        left, right = old[old_pos], new[new_pos]
        matched_old.add(old_pos)
        matched_new.add(new_pos)
        matched += 1
        changed = {field: {"feedhub": left[field], "homesector": right[field]}
                   for field in FIELDS
                   if _value(field, left[field]) != _value(field, right[field])}
        differences.update(changed.keys())
        if changed and len(samples) < sample_limit:
            samples.append({"id": right["id"], "link": right["link"], "changes": changed})
    only_old = [row for i, row in enumerate(old) if i not in matched_old]
    only_new = [row for i, row in enumerate(new) if i not in matched_new]
    return {"status": "compared_real_snapshots", "feedhub_items": len(old),
            "homesector_items": len(new), "matched_variants": matched,
            "only_feedhub": len(only_old), "only_homesector": len(only_new),
            "field_differences": dict(sorted(differences.items())),
            "feedhub_duplicate_ids": len(old) - len({r["id"] for r in old}),
            "homesector_duplicate_ids": len(new) - len({r["id"] for r in new}),
            "feedhub_availability": dict(Counter(r["availability"] for r in old)),
            "homesector_availability": dict(Counter(r["availability"] for r in new)),
            "only_feedhub_samples": only_old[:sample_limit],
            "only_homesector_samples": only_new[:sample_limit],
            "difference_samples": samples, "destination_subscriptions_changed": False}
