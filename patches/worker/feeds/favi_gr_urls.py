"""Read-only verification of public Greek product landing pages."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote, urlparse
import requests
from .favi_gr_rate_limit import storefront_limiter


def _translated_handle(translations):
    for item in translations or []:
        if item.get("key") == "handle" and item.get("value"):
            return str(item["value"]).strip()
    return ""


def _check_handle(handle, domain="homesector.gr"):
    if not handle or "/" in handle or "?" in handle or "#" in handle:
        return False, "invalid_handle", None
    expected = "/products/" + handle
    try:
        response = storefront_limiter.get("https://" + domain + "/products/" + quote(handle, safe="-"),
                                timeout=15, allow_redirects=True,
                                headers={"User-Agent": "HomesectorFeedVerifier/1.0"})
        if response.status_code != 200:
            # Keep the exact HTTP status in the aggregate report. A 404 needs
            # storefront routing work, while a 429/5xx needs rate/edge work.
            return False, f"http_{response.status_code}", None
        final = urlparse(response.url)
        if final.scheme != "https" or final.hostname != domain:
            return False, "wrong_domain", None
        if unquote(final.path).rstrip("/") != expected:
            return False, "redirected_path", None
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            return False, "not_html", None
        if handle not in response.text:
            return False, "missing_handle_in_page", None
        return True, "verified", "https://" + domain + "/products/" + quote(handle, safe="-")
    except requests.RequestException:
        return False, "request_failed", None


def check_one(product, translated_handle="", domain="homesector.gr"):
    source_handle = str(product.get("handle") or "")
    source = _check_handle(source_handle, domain)
    if source[0]:
        return source
    if translated_handle and translated_handle != source_handle:
        translated = _check_handle(translated_handle, domain)
        if translated[0]:
            return translated
    return source


def verify_one(product):
    return check_one(product)[0]


def verify_market_urls(products, category_by_product, workers=8, translated_map=None,
                       market="GR"):
    if market not in ("GR", "RO"):
        raise ValueError("Unsupported FAVI URL market")
    domain = "homesector." + ("gr" if market == "GR" else "ro")
    candidates = [p for p in products if p.get("id") in category_by_product]
    if not 1 <= workers <= 16:
        raise ValueError("Invalid URL verification concurrency")
    verified = {}
    reasons = Counter()
    samples = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                check_one, product,
                _translated_handle((translated_map or {}).get(product["id"], {}).get(market, [])),
                domain
            ): product["id"] for product in candidates
        }
        for future in as_completed(futures):
            valid, reason, url = future.result()
            reasons[reason] += 1
            if not valid and len(samples.get(reason, [])) < 3:
                samples.setdefault(reason, []).append(next(
                    p.get("handle") for p in candidates if p["id"] == futures[future]))
            if valid:
                verified[futures[future]] = url
    return verified, {"checked": len(candidates), "verified": len(verified),
                      "reasons": dict(sorted(reasons.items())),
                      "sample_handles": samples}

