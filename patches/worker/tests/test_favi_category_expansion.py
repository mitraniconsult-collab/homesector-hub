from feeds.favi_gr_taxonomy import categories_for_products as greek_categories
from feeds.favi_ro_taxonomy import categories_for_products as romanian_categories


def test_reviewed_tableware_and_food_container_leaves():
    products = [
        {"id": "p-bowl", "category": {"id": "gid://shopify/TaxonomyCategory/hg-11-10-4-1"}},
        {"id": "p-plate", "category": {"id": "gid://shopify/TaxonomyCategory/hg-11-10-4-3"}},
        {"id": "p-container", "category": {"id": "gid://shopify/TaxonomyCategory/hg-11-4-6"}},
        {"id": "gid://shopify/Product/8730408747275",
         "category": {"id": "gid://shopify/TaxonomyCategory/hg-11-4-6"}},
    ]
    ro = romanian_categories(products)
    gr = greek_categories(products, {})
    assert {"p-bowl", "p-plate", "p-container"} <= ro.keys()
    assert "gid://shopify/Product/8730408747275" not in ro
    assert gr["p-plate"]["path"] == "Πιατικά > Πιάτα σερβιρίσματος"


def test_unverified_generic_category_stays_excluded():
    product = {"id": "p-generic", "category": {"id": "gid://shopify/TaxonomyCategory/hg-3"}}
    assert romanian_categories([product]) == {}
    assert greek_categories([product], {}) == {}
