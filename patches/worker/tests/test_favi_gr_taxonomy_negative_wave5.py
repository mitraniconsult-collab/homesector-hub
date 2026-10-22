"""Keep mixed Shopify leaves out of automatic FAVI Greece mapping."""
from feeds.favi_gr_taxonomy import categories_for_products


def test_mixed_leaves_remain_unmapped():
    mixed = (
        "hg-11-10-4-3",  # plates leaf also contained bowls and platters
        "hg-11-10-5",    # drinkware parent
        "hg-3-30",      # figurines leaf includes jars and other decor
        "fr-14",        # ottomans leaf includes stools and storage seats
        "hg-3-6",      # decor baskets leaf includes boxes and table set
        "fr-19-1",     # bookcases parent includes wine, shoe, kitchen racks
        "hg-15-1",     # bedding parent includes bedspreads
        "hg-3-18",     # coat racks leaf mixes wall and floor models
        "bt-5-7-1",    # night lights leaf contains pendants and garlands
        "hg-11-8-45",  # kitchen utensil sets leaf contains flatware
        "hg-3-58",     # seasonal decor leaf contains unrelated items
    )
    products = [
        {"id": key, "category": {"id": f"gid://shopify/TaxonomyCategory/{key}"}}
        for key in mixed
    ]
    assert categories_for_products(products, {}) == {}
