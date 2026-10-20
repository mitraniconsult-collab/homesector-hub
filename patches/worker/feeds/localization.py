"""Apply existing verified Shopify translations; never invent translated product content."""
from .markets_normalize import plain_text
from .config import MARKETS

KEYS = {"title", "body_html", "handle"}

def apply_verified_translations(row, translations, market, url_verified=False):
    if market not in MARKETS:
        raise ValueError("Unsupported market")
    new_row = dict(row)
    if market == "BG":
        new_row["verified_locale"] = "bg"
        new_row["verified_market_url"] = True
        return new_row
    localized = {
        item.get("key"): item.get("value")
        for item in (translations or [])
        if item and item.get("key") in KEYS and item.get("value")
    }
    if localized.get("title"):
        new_row["title"] = localized["title"].strip()
    if localized.get("body_html"):
        new_row["description"] = plain_text(localized["body_html"])
    # Both title and description must exist as translations.
    if localized.get("title") and localized.get("body_html"):
        new_row["verified_locale"] = MARKETS[market]["language"]
    # Do not assume that a Shopify handle translation is available or that
    # the market domain resolves to this product without verification.
    new_row["verified_market_url"] = bool(url_verified)
    return new_row
