"""Collection-context links require Shopify membership and an exact GR landing page."""
from unittest.mock import Mock, patch
from feeds import favi_gr_collection_urls as urls


def test_collection_fallback_accepts_only_exact_greek_product_path():
    product = {"id": "gid://shopify/Product/1", "handle": "box-one"}
    data = {"nodes": [{"id": product["id"], "handle": product["handle"],
                       "collections": {"nodes": [{"handle": "storage"}]}}]}
    good = Mock(status_code=200,
                url="https://homesector.gr/collections/storage/products/box-one",
                headers={"Content-Type": "text/html"}, text="box-one")
    wrong = Mock(status_code=200,
                 url="https://homesector.bg/collections/storage/products/box-one",
                 headers={"Content-Type": "text/html"}, text="box-one")
    with patch.object(urls, "post_graphql", return_value=data), \
            patch.object(urls.requests, "get", return_value=good):
        verified, report = urls.verify_collection_urls(
            [product], set(), "example.myshopify.com", "token")
    assert verified[product["id"]] == good.url
    assert report["verified"] == 1
    with patch.object(urls.requests, "get", return_value=wrong):
        assert urls._check(product, ["storage"]) is None


def test_category_collection_after_brand_memberships_is_considered():
    product = {"id": "gid://shopify/Product/1", "handle": "edie-zhakard"}
    collections = [{"handle": h} for h in (
        "atmosphera", "allproducts", "bedroom", "new-arrivals",
        "clearance", "текстил-за-спалня-category")]
    response = {"nodes": [{"id": product["id"], "handle": product["handle"],
                           "collections": {"nodes": collections,
                                           "pageInfo": {"hasNextPage": False}}}]}
    with patch.object(urls, "post_graphql", return_value=response) as query:
        result = urls._candidates([product], {product["id"]},
                                  "example.myshopify.com", "token")
    assert result[product["id"]][0] == "текстил-за-спалня-category"
    assert "collections(first: 20)" in query.call_args.args[2]
