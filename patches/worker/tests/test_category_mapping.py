from feeds.category_mapping import apply_category, category_candidate

PRODUCT = {
    "productType": "",
    "category": {"id": "gid://shopify/TaxonomyCategory/hg-11-2-3-13-1",
                 "fullName": "Home & Garden > Kitchen & Dining > Cookware > Frying Pans"},
}

def test_english_taxonomy_is_a_candidate_not_a_verified_bg_category():
    candidate = category_candidate(PRODUCT, "BG")
    assert candidate["source"] == "shopify_standard_taxonomy"
    assert candidate["verified_for_market"] is False
    row = apply_category({"id": "1", "product_type": ""}, PRODUCT, "BG")
    assert row["product_type"] is None
    assert row["category_candidate"].endswith("Frying Pans")

def test_market_validated_category_is_usable():
    row = apply_category({"id": "1"}, PRODUCT, "BG", "Тигани")
    assert row["product_type"] == "Тигани"
    assert row["category_verified_for_market"] is True

def test_market_isolation():
    candidate = category_candidate({"productType": "Frying pans"}, "RO")
    assert not candidate["verified_for_market"]
