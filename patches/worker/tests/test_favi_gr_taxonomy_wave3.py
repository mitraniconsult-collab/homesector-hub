"""Exact FAVI Greece kitchen and furniture category coverage."""
from feeds.favi_gr_taxonomy import categories_for_products


def test_favi_gr_wave3_exact_categories_do_not_infer_parent_shelves_or_baskets():
    expected = {
        "hg-11-10-4-1": "Μπολ",
        "fr-4-14-1-1": "Ντουλάπια μπάνιου",
        "fr-7-1-1": "Πολυθρόνες",
        "fr-15-4-5": "Ξαπλώστρες κήπου",
        "hg-3-15": "Μαξιλάρια για έπιπλα",
    }
    products = [
        {"id": key, "category": {"id": f"gid://shopify/TaxonomyCategory/{key}"}}
        for key in (*expected, "hg-3-6", "fr-19-1", "fr-19-1-4")
    ]
    mapped = categories_for_products(products, {})
    assert set(mapped) == set(expected)
    assert all(mapped[key] == {"market": "GR", "verified": True, "path": path}
               for key, path in expected.items())
