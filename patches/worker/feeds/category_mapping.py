"""Source a real category from Shopify taxonomy rather than inventing one.

FAVI category paths must be local-language validated before publishing.
"""
from .config import MARKETS

def category_candidate(product, market):
    if market not in MARKETS:
        raise ValueError("Unsupported market")
    taxonomy = product.get("category") or {}
    full = str(taxonomy.get("fullName") or "").strip()
    current = str(product.get("productType") or "").strip()
    if current:
        return {"candidate": current, "source": "shopify_product_type",
                "taxonomy_id": taxonomy.get("id"), "verified_for_market": False}
    if full:
        return {"candidate": full, "source": "shopify_standard_taxonomy",
                "taxonomy_id": taxonomy.get("id"), "verified_for_market": False}
    return {"candidate": None, "source": "missing",
            "taxonomy_id": None, "verified_for_market": False}

def apply_category(row, product, market, validated_market_category=None):
    copy = dict(row)
    chosen = category_candidate(product, market)
    if validated_market_category and str(validated_market_category).strip():
        copy["product_type"] = str(validated_market_category).strip()
        copy["category_verified_for_market"] = True
    else:
        copy["category_candidate"] = chosen["candidate"]
        copy["category_source"] = chosen["source"]
        copy["category_verified_for_market"] = chosen["verified_for_market"]
        # Keep unverified taxonomy as audit evidence, not a published category.
        if not chosen["verified_for_market"]:
            copy["product_type"] = None
    return copy
