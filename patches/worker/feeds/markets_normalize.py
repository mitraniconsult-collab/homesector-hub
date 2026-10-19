"""Convert country-context Shopify records to feed-ready variant rows."""
import re
from html import unescape
from .config import MARKETS

def plain_text(html):
    return unescape(re.sub(r"<[^>]+>", " ", html or "")).strip()

def normalize_market(product, country):
    if country not in MARKETS:
        raise ValueError("Unsupported country")
    if product.get("status") != "ACTIVE" or not product.get("published_" + country):
        return []
    handle = product.get("handle")
    if not handle:
        return []
    output = []
    for variant in product.get("variants", {}).get("nodes", []):
        money = (variant.get("price_" + country) or {}).get("price") or {}
        if money.get("currencyCode") != MARKETS[country]["currency"]:
            continue
        if not money.get("amount"):
            continue
        image = (variant.get("image") or product.get("featuredImage") or {}).get("url")
        if not image:
            continue
        quantity = variant.get("inventoryQuantity") or 0
        output.append({
            "id": variant.get("id"), "title": product.get("title"),
            "description": plain_text(product.get("descriptionHtml")),
            "link": "https://" + MARKETS[country]["domain"] + "/products/" + handle
                    + "?variant=" + str(variant.get("id", "").rsplit("/", 1)[-1]),
            "image_link": image, "brand": product.get("vendor"),
            "product_type": product.get("productType"),
            "gtin": variant.get("barcode"), "mpn": variant.get("sku"),
            "price": money["amount"], "currency": money["currencyCode"],
            "active": True, "published": True, "available": quantity > 0,
            "continue_selling": variant.get("inventoryPolicy") == "CONTINUE",
            "markets": [country],
        })
    return output
