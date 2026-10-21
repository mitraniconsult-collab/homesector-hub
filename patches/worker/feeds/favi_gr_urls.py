"""Read-only verification of public Greek product landing pages."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests


def check_one(product):
    handle = str(product.get("handle") or "")
    if not handle or "/" in handle or "?" in handle or "#" in handle:
        return False, "invalid_handle"
    expected = "/products/" + handle
    try:
        response = requests.get("https://homesector.gr" + expected,
                                timeout=15, allow_redirects=True,
                                headers={"User-Agent": "HomesectorFeedVerifier/1.0"})
        final = urlparse(response.url)
        if response.status_code != 200:
            return False, "non_200"
        if final.scheme != "https" or final.hostname != "homesector.gr":
            return False, "wrong_domain"
        if final.path.rstrip("/") != expected:
            return False, "redirected_path"
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            return False, "not_html"
        if handle not in response.text:
            return False, "missing_handle_in_page"
        return True, "verified"
    except requests.RequestException:
        return False, "request_failed"


def verify_one(product):
    return check_one(product)[0]


def verify_market_urls(products, category_by_product, workers=8):
    candidates = [p for p in products if p.get("id") in category_by_product]
    if not 1 <= workers <= 16:
        raise ValueError("Invalid URL verification concurrency")
    verified = set()
    reasons = Counter()
    samples = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_one, product): product["id"] for product in candidates}
        for future in as_completed(futures):
            valid, reason = future.result()
            reasons[reason] += 1
            if not valid and len(samples.get(reason, [])) < 3:
                samples.setdefault(reason, []).append(next(
                    p.get("handle") for p in candidates if p["id"] == futures[future]))
            if valid:
                verified.add(futures[future])
    return verified, {"checked": len(candidates), "verified": len(verified),
                      "reasons": dict(sorted(reasons.items())),
                      "sample_handles": samples}
