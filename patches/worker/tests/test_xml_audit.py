from feeds.xml_audit import validate_xml
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
    row = {**good_row(), "available": False, "continue_selling": True}
    for date in (None, "", "tomorrow", "2026-12-01T12:00:00"):
        content = generate([{**row, "availability_date": date}], "BG", "google")
        report = validate_xml(content)
        assert not report["passed"]
        assert report["issues"]["invalid_backorder_availability_date"] == 1
    content = generate([{**row, "availability_date": "2026-12-01T12:00:00+02:00"}], "BG", "google")
    assert validate_xml(content)["passed"]
