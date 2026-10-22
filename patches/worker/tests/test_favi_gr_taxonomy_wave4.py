"""FAVI Greece wall-clock and modular-shelf review coverage."""
from feeds.favi_gr_taxonomy import categories_for_products


def test_wave4_exact_leaves_and_misclassified_storage_box_exclusion():
    products = [
        {"id": "clock", "category": {"id": "gid://shopify/TaxonomyCategory/hg-3-17-4"}},
        {"id": "shelf", "category": {"id": "gid://shopify/TaxonomyCategory/fr-19-1-4"}},
        {"id": "gid://shopify/Product/10728260010251",
         "category": {"id": "gid://shopify/TaxonomyCategory/fr-19-1-4"}},
        {"id": "generic-shelf", "category": {"id": "gid://shopify/TaxonomyCategory/fr-19-1"}},
    ]
    mapped = categories_for_products(products, {})
    assert mapped == {
        "clock": {"market": "GR", "verified": True, "path": "Ρολόγια"},
        "shelf": {"market": "GR", "verified": True, "path": "Ραφιέρες"},
    }
