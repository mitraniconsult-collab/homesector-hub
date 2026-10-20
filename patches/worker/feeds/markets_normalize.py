"""Convert country-context Shopify records to feed-ready variant rows."""
import re
from html import unescape
from .config import MARKETS
from .availability import arrival_timestamp, feed_availability

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
        arrival = (variant.get("expectedArrival") or {}).get("value")
        if not arrival and (product.get("variantsCount") or {}).get("count") == 1:
            arrival = (product.get("expectedArrival") or {}).get("value")
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
            "markets": [country], "inventory_quantity": quantity,
            "expected_arrival": arrival, "availability_date": arrival_timestamp(arrival),
        })
        output[-1]["availability"] = feed_availability(output[-1])
    return output
