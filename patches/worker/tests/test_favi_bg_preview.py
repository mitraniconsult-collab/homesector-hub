import json
from xml.etree import ElementTree as ET

from feeds.favi_bg_preview import create_preview


def test_legacy_id_migration_stays_private_and_measured(tmp_path):
    source = tmp_path / "google-bg"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({"finished": True, "items": 2}))
    category = tmp_path / "favi-shopify-categories"
    category.mkdir()
    (category / "manifest.json").write_text(json.dumps({"finished": True}))
    (category / "products.jsonl").write_text(json.dumps({
        "handle": "masa", "category_name": "Home & Garden > Decor > Vases",
    }) + "\n")
    rows = []
    for variant in (17, 18):
        rows.append({
            "id": f"gid://shopify/ProductVariant/{variant}",
            "item_group_id": "shopifyp12", "title": f"Ваза {variant}",
            "description": "Керамична ваза", "link": f"https://homesector.bg/products/masa?variant={variant}",
            "image_link": "https://cdn.shopify.com/a.jpg", "price": "54.00",
            "currency": "EUR", "active": True, "published": True,
            "markets": ["BG"], "available": True, "continue_selling": False,
        })
    (source / "records.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n")
    (tmp_path / "favi-historical-id-matches.json").write_text(json.dumps([
        {"new_shopify_gid": rows[0]["id"], "legacy_favi_candidate_id": "old-17"},
    ]))

    report = create_preview(tmp_path)
    assert report["xml_items"] == 1
    assert report["blocked_legacy_id_migration"] == 1
    assert report["id_migration_candidate_items"] == 2
    assert report["published"] is False
    ns = {"g": "http://base.google.com/ns/1.0"}
    main = ET.parse(tmp_path / "favi-bg-unpublished.xml")
    candidate = ET.parse(tmp_path / "favi-bg-id-migration-candidate.xml")
    assert [e.findtext("g:id", namespaces=ns) for e in main.findall("./channel/item")] == ["shopifyv18"]
    assert {e.findtext("g:id", namespaces=ns) for e in candidate.findall("./channel/item")} == {"shopifyv17", "shopifyv18"}
