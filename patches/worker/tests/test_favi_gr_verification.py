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
    assert ids == set() and report == {"checked": 1, "verified": 0}
