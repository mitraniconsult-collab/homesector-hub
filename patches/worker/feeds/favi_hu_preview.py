"""Private FAVI Hungary preview; never submits products to FAVI."""
from .favi_xml import generate_favi
from .market_feed_rows import prepare_market_rows


def create_preview(products, category_by_product, verified_url_ids,
                   translated_map=None, translated_variant_map=None):
    products = list(products)
    rows, exclusions = prepare_market_rows(
        products, "HU", "favi", verified_url_ids=verified_url_ids,
        translated_map=translated_map,
        translated_variant_map=translated_variant_map,
        category_by_product=category_by_product)
    xml, serialized = generate_favi(rows, "HU")
    return xml, {
        "market": "HU", "status": "unpublished_preview",
        "source_products": len(products), "candidate_rows": len(rows),
        "xml_items": serialized["items_exported"],
        "preflight_exclusions": exclusions,
        "serializer_exclusions": serialized["excluded_reasons"],
        "approved_by_favi": False, "published": False,
    }
