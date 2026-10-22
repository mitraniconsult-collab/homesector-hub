"""FAVI Greece checks before a public preview pointer is changed."""
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET

G = "{http://base.google.com/ns/1.0}"


def audit_favi_gr(xml, max_examples=5):
    root = ET.fromstring(xml)
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise ValueError("Invalid FAVI GR RSS structure")
    issues = Counter()
    examples = defaultdict(list)
    seen_links = set()
    signatures = defaultdict(set)
    ambiguous_groups = set()
    items = channel.findall("item")
    for item in items:
        item_id = (item.findtext(G + "id") or "").strip()
        link = (item.findtext("link") or "").strip()
        category = (item.findtext(G + "product_type") or "").strip()
        group = (item.findtext(G + "item_group_id") or "").strip()
        for reason, missing in (
            ("missing_product_link", not link),
            ("duplicate_product_link", bool(link) and link in seen_links),
            ("missing_favi_category", not category),
            ("missing_parent_group", not group),
        ):
            if missing:
                issues[reason] += 1
                if len(examples[reason]) < max_examples:
                    examples[reason].append(item_id)
        seen_links.add(link)
        if group:
            signature = tuple((item.findtext(key) or "").strip() for key in
                              ("title", "description", G + "color"))
            if signature in signatures[group]:
                ambiguous_groups.add(group)
            signatures[group].add(signature)
    return {
        "items": len(items),
        "passed": bool(items) and not issues,
        "issues": dict(sorted(issues.items())),
        "issue_examples": dict(sorted(examples.items())),
        "warnings": {
            "indistinguishable_variant_groups": len(ambiguous_groups),
            "sample_group_ids": sorted(ambiguous_groups)[:max_examples],
        },
    }
