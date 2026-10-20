from feeds.xml_audit import validate_xml, validated_preview, G
from xml.etree import ElementTree as ET
from feeds.xml_export import generate

def good_row():
    return {
        "id": "shopify-v123", "title": "Тиган", "description": "Алуминиев тиган",
        "link": "https://homesector.bg/products/pan?variant=123",
        "image_link": "https://cdn.shopify.com/pan.jpg", "price": "25.00",
        "currency": "EUR", "brand": "Quttin", "active": True, "published": True,
        "markets": ["BG"], "available": True, "continue_selling": False,
    }

def test_healthy_google_feed_passes():
    report = validate_xml(generate([good_row()], "BG", "google"), "BG")
    assert report["passed"] is True
    assert report["items"] == 1
    assert report["submitted"] is False

def test_duplicate_ids_cannot_pass():
    row = good_row()
    report = validate_xml(generate([row,row], "BG", "google"), "BG")
    assert report["passed"] is False
    assert report["issues"]["duplicate_or_blank_id"] == 1

def test_wrong_country_domain_cannot_pass():
    row = {**good_row(), "link": "https://homesector.ro/products/pan?variant=123"}
    report = validate_xml(generate([row], "BG", "google"), "BG")
    assert report["issues"]["wrong_market_link"] == 1


def test_backorder_requires_timezone_aware_availability_date():
    row = {**good_row(), "available": False, "continue_selling": True, "availability": "backorder"}
    for date in (None, "", "tomorrow", "2026-12-01T12:00:00"):
        content = generate([{**row, "availability_date": date}], "BG", "google")
        report = validate_xml(content)
        assert not report["passed"]
        assert report["issues"]["invalid_backorder_availability_date"] == 1
    content = generate([{**row, "availability_date": "2026-12-01T12:00:00+02:00"}], "BG", "google")
    assert validate_xml(content)["passed"]


def test_private_preview_preserves_valid_ids_and_reports_all_exclusions():
    healthy = good_row()
    backorder = {**healthy, "id": "backordered", "available": False, "continue_selling": True, "availability": "backorder"}
    missing = {**healthy, "id": "missing", "description": ""}
    source = generate([healthy, backorder, missing, healthy], "BG", "google")
    preview, report = validated_preview(source)
    assert report["items"] == 1 and report["excluded_rows"] == 3
    assert report["quality_passed"] and not report["published"]
    assert report["issues"] == {"invalid_backorder_availability_date": 1,
                                "missing_description": 1, "duplicate_or_blank_id": 1}
    assert ET.fromstring(preview).findtext("./channel/item/" + G + "id") == healthy["id"]
    assert len(ET.fromstring(source).findall("./channel/item")) == 4


def test_empty_validated_preview_does_not_pass_quality():
    source = generate([{**good_row(), "description": ""}], "BG", "google")
    _, report = validated_preview(source)
    assert report["items"] == 0 and not report["quality_passed"]
