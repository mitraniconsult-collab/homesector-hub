"""Coverage for reviewed FAVI Greece taxonomy leaves."""
from feeds.favi_gr_taxonomy import categories_for_products


def test_new_exact_leaves_are_mapped_without_broad_parent_fallback():
    leaves = {
        "hg-3-67": "Διακοσμητικά βάζα",
        "hg-3-2": "Τεχνητά διακοσμητικά φυτά",
        "hg-13-5-1": "Επιτραπέζια φωτιστικά",
        "hg-13-9-5": "Κρεμαστά φωτιστικά",
        "hg-3-74-1-1": "Κουρτίνες",
        "fr-15-4-2": "Καρέκλες κήπου",
        "hg-3-52": "Κορνίζες",
        "fr-7-9": "Καρέκλες τραπεζαρίας",
        "hg-13-5-3": "Φωτιστικά δαπέδου",
        "hg-1-15": "Δοχεία σαπουνιού",
    }
    products = [
        {"id": leaf, "category": {"id": f"gid://shopify/TaxonomyCategory/{leaf}"}}
        for leaf in leaves
    ]
    products.append({"id": "drinkware", "category": {"id": "gid://shopify/TaxonomyCategory/hg-11-10-5"}})
    mapped = categories_for_products(products, {"hg-3-67": {"path": "Manual review", "verified": True}})
    assert set(mapped) == set(leaves)
    assert mapped["hg-3-67"]["path"] == "Manual review"
    for leaf, path in leaves.items():
        if leaf != "hg-3-67":
            assert mapped[leaf] == {"market": "GR", "verified": True, "path": path}
