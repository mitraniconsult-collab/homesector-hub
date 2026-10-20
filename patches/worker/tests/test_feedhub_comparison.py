from xml.etree import ElementTree as ET
import pytest
from feeds.feedhub_comparison import compare_snapshots, reconcile_ids
from feeds.xml_export import generate, GOOGLE_NS
from test_xml_audit import good_row


def feed(*rows):
    return generate(rows, "BG", "google")


def test_same_variant_preserves_legacy_id_even_after_handle_change():
    old = {**good_row(), "id": "legacy-17", "link": "https://homesector.bg/products/old?variant=123&utm_source=feedhub"}
    new = {**good_row(), "id": "gid://shopify/ProductVariant/123", "link": "https://homesector.bg/products/new?variant=123"}
    xml, continuity = reconcile_ids(feed(old), feed(new))
    assert continuity["historical_ids_preserved"] == 1
    assert ET.fromstring(xml).findtext("./channel/item/{" + GOOGLE_NS + "}id") == "legacy-17"
    comparison = compare_snapshots(feed(old), xml)
    assert comparison["matched_variants"] == 1
    assert comparison["field_differences"] == {"link": 1}


def test_real_price_and_availability_differences_and_missing_rows():
    common = {**good_row(), "id": "same"}
    added = {**common, "id": "added", "link": "https://homesector.bg/products/added?variant=2"}
    removed = {**common, "id": "removed", "link": "https://homesector.bg/products/removed?variant=3"}
    current = {**common, "price": "30.00", "available": False, "continue_selling": True,
               "availability": "backorder", "availability_date": "2026-12-16T00:00:00+02:00"}
    report = compare_snapshots(feed(common, removed), feed(current, added))
    assert report["only_feedhub"] == 1 and report["only_homesector"] == 1
    assert report["field_differences"] == {"availability": 1, "price": 1}
    assert report["matched_variants"] == 1
    assert not report["destination_subscriptions_changed"]


def test_price_format_and_tracking_query_are_not_false_differences():
    old = {**good_row(), "price": "25", "link": good_row()["link"] + "&utm_source=feedhub"}
    report = compare_snapshots(feed(old), feed(good_row()))
    assert report["field_differences"] == {}


def test_ambiguous_variant_does_not_silently_borrow_an_id():
    old = good_row()
    data, report = reconcile_ids(feed(old, {**old, "id": "other"}), feed(old))
    assert report["ambiguous_matches"] == 1
    assert report["historical_ids_preserved"] == 0


def test_reconciled_id_collision_blocks_publishing():
    old = {**good_row(), "id": "collision"}
    new = {**good_row(), "id": "new"}
    extra = {**good_row(), "id": "collision", "link": "https://homesector.bg/products/x?variant=2"}
    with pytest.raises(ValueError, match="duplicate"):
        reconcile_ids(feed(old), feed(new, extra))
