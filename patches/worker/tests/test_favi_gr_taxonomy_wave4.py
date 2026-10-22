"""FAVI Greece wall-clock and modular-shelf review coverage."""
from feeds.favi_gr_taxonomy import categories_for_products


def test_wave4_exact_leaves_and_corrected_storage_box_category():
    products = [
        {"id": "clock", "category": {"id": "gid://shopify/TaxonomyCategory/hg-3-17-4"}},
        {"id": "shelf", "category": {"id": "gid://shopify/TaxonomyCategory/fr-19-1-4"}},
        {"id": "gid://shopify/Product/10728260010251",
         "category": {"id": "gid://shopify/TaxonomyCategory/hg-10-16-10"}},
        {"id": "generic-shelf", "category": {"id": "gid://shopify/TaxonomyCategory/fr-19-1"}},
    ]
    mapped = categories_for_products(products, {})
    assert mapped == {
        "clock": {"market": "GR", "verified": True, "path": "Ρολόγια"},
        "shelf": {"market": "GR", "verified": True, "path": "Ραφιέρες"},
        "gid://shopify/Product/10728260010251": {
            "market": "GR", "verified": True,
            "path": "Κουτιά αποθήκευσης και οργάνωσης > Καλάθια αποθήκευσης"},
    }
