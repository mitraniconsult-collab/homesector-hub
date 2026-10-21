"""Private FAVI Greece candidate from actual GR-context Shopify product rows.

Requires explicitly checked Greek categories and verified Greek landing links.
No destination publication or FAVI account mutation is performed here.
"""
from .favi_xml import generate_favi
from .market_feed_rows import prepare_market_rows


def create_preview(products, category_by_product, verified_url_ids,
                   translated_map=None, translated_variant_map=None):
    products = list(products)
    rows, exclusions = prepare_market_rows(
        products, "GR", "favi", verified_url_ids=verified_url_ids,
        translated_map=translated_map,
        translated_variant_map=translated_variant_map,
        category_by_product=category_by_product)
    xml, serialized = generate_favi(rows, "GR")
    return xml, {
        "market": "GR", "status": "unpublished_preview",
        "source_products": len(products),
        "candidate_rows": len(rows),
        "xml_items": serialized["items_exported"],
        "preflight_exclusions": exclusions,
        "serializer_exclusions": serialized["excluded_reasons"],
        "approved_by_favi": False, "published": False,
    }
