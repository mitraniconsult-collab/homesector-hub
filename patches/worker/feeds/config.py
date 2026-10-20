"""Feed configuration and catalog eligibility checks."""
from urllib.parse import urlparse

MARKETS = {
    "BG": {"language": "bg", "currency": "EUR", "domain": "homesector.bg"},
    "RO": {"language": "ro", "currency": "RON", "domain": "homesector.ro"},
    "GR": {"language": "el", "currency": "EUR", "domain": "homesector.gr"},
    "HU": {"language": "hu", "currency": "HUF", "domain": "homesector.hu"},
}
CHANNELS = ("google", "meta", "favi", "biano")


def eligible(product, market):
    if market not in MARKETS:
        raise ValueError("Unsupported market")
    if not product.get("active") or not product.get("published"):
        return False
    if market not in product.get("markets", []):
        return False
    if not (product.get("available") or product.get("continue_selling")):
        return False
    if not all(product.get(key) for key in ("id", "title", "price", "link", "image_link")):
        return False
    if product.get("currency") != MARKETS[market]["currency"]:
        return False
    for field in ("link", "image_link"):
        parsed = urlparse(product[field])
        if parsed.scheme != "https" or not parsed.netloc:
            return False
    return True
