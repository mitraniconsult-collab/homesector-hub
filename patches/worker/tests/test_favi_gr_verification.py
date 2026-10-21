"""FAVI Greece category and landing URL gates."""
from unittest.mock import patch
from feeds.favi_gr_taxonomy import categories_for_products
from feeds.favi_gr_urls import verify_market_urls


def test_reviewed_taxonomy_maps_only_known_id():
    products = [{"id": "p1", "category": {"id": "gid://shopify/TaxonomyCategory/hg-11-4-6"}},
                {"id": "p2", "category": {"id": "unknown"}}]
    mapped = categories_for_products(products, {})
    assert mapped["p1"]["path"] == "Αποθήκευση τροφίμων > Δοχεία τροφίμων"
    assert mapped["p1"]["verified"] is True
    assert "p2" not in mapped


def test_public_url_check_rejects_redirected_domain():
    class Response:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        text = "<html><body>hello-chair</body></html>"
        url = "https://other.example/products/hello-chair"
    product = {"id": "p1", "handle": "hello-chair"}
    with patch("feeds.favi_gr_urls.requests.get", return_value=Response()):
        ids, report = verify_market_urls([product], {"p1": {"verified": True}}, workers=1)
    assert ids == {} and report["checked"] == 1 and report["verified"] == 0
    assert report["reasons"] == {"wrong_domain": 1}


def test_public_url_check_accepts_percent_encoded_cyrillic_handle():
    class Response:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        text = "<html><body>кутия</body></html>"
        url = "https://homesector.gr/products/%D0%BA%D1%83%D1%82%D0%B8%D1%8F"
    product = {"id": "p2", "handle": "кутия"}
    with patch("feeds.favi_gr_urls.requests.get", return_value=Response()):
        ids, report = verify_market_urls([product], {"p2": {"verified": True}}, workers=1)
    assert ids == {"p2": "https://homesector.gr/products/%D0%BA%D1%83%D1%82%D0%B8%D1%8F"} and report["verified"] == 1


def test_translated_handle_is_verified_and_used_for_link():
    class Response:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        text = "<html><body>kouti-apothikeusis</body></html>"
        url = "https://homesector.gr/products/kouti-apothikeusis"
    product = {"id": "p3", "handle": "kutiya-za-sahranenie"}
    translated = {"p3": {"GR": [{"key": "handle", "value": "kouti-apothikeusis"}]}}
    with patch("feeds.favi_gr_urls.requests.get", return_value=Response()) as get:
        urls, report = verify_market_urls(
            [product], {"p3": {"verified": True}}, workers=1,
            translated_map=translated)
    assert urls == {"p3": "https://homesector.gr/products/kouti-apothikeusis"}
    assert report["verified"] == 1
    assert get.call_count == 2



def test_http_failure_report_preserves_status_code():
    class Response:
        status_code = 429
        url = "https://homesector.gr/products/hello-chair"
        headers = {"Content-Type": "text/html"}
        text = "Too many requests"
    product = {"id": "p4", "handle": "hello-chair"}
    with patch("feeds.favi_gr_urls.requests.get", return_value=Response()):
        urls, report = verify_market_urls([product], {"p4": {"verified": True}}, workers=1)
    assert urls == {}
    assert report["reasons"] == {"http_429": 1}
    assert report["sample_handles"]["http_429"] == ["hello-chair"]
