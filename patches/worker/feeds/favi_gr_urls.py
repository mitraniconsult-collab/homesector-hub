"""Read-only verification of public Greek product landing pages."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests


def verify_one(product):
    handle = str(product.get("handle") or "")
    if not handle or "/" in handle or "?" in handle or "#" in handle:
        return False
    expected = "/products/" + handle
    try:
        response = requests.get("https://homesector.gr" + expected,
                                timeout=15, allow_redirects=True,
                                headers={"User-Agent": "HomesectorFeedVerifier/1.0"})
        final = urlparse(response.url)
        return (response.status_code == 200 and final.scheme == "https"
                and final.hostname == "homesector.gr"
                and final.path.rstrip("/") == expected
                and "text/html" in response.headers.get("Content-Type", "").lower()
                and handle in response.text)
    except requests.RequestException:
        return False


def verify_market_urls(products, category_by_product, workers=8):
    candidates = [p for p in products if p.get("id") in category_by_product]
    if not 1 <= workers <= 16:
        raise ValueError("Invalid URL verification concurrency")
    verified = set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(verify_one, product): product["id"] for product in candidates}
        for future in as_completed(futures):
            if future.result():
                verified.add(futures[future])
    return verified, {"checked": len(candidates), "verified": len(verified)}
