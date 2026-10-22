"""Read-only quality gate for proposed feed targets.

Do not treat source-language titles as localized translations. Every target must
pass its own market, category and channel checks before external publishing.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from .config import MARKETS
from .targets import enabled

VALID_CHANNELS = {"google", "meta", "favi", "biano"}
REQUIRED_FIELDS = ("id", "title", "description", "link", "image_link", "price", "currency")

def check_product(row, market, channel):
    if market not in MARKETS or channel not in VALID_CHANNELS or not enabled(channel, market):
        raise ValueError("Unsupported feed target")
    problems = []
    for field in REQUIRED_FIELDS:
        if row.get(field) is None or not str(row[field]).strip():
            problems.append("missing_" + field)
    if not row.get("active") or not row.get("published") or market not in (row.get("markets") or []):
        problems.append("not_published_in_market")
    if not row.get("available") and not row.get("continue_selling"):
        problems.append("not_sellable")
    if row.get("currency") != MARKETS[market]["currency"]:
        problems.append("wrong_currency")
    try:
        if Decimal(str(row.get("price"))) <= 0:
            problems.append("invalid_price")
    except (InvalidOperation, TypeError, ValueError):
        problems.append("invalid_price")
    if row.get("link") and urlparse(str(row["link"])).hostname != MARKETS[market]["domain"]:
        problems.append("wrong_market_domain")
    for field in ("link", "image_link"):
        if row.get(field):
            u = urlparse(str(row[field]))
            if u.scheme != "https" or not u.netloc:
                problems.append("invalid_" + field)
    if channel == "favi" and not row.get("product_type"):
        problems.append("missing_favi_category")
    if channel == "favi" and not row.get("category_verified_for_market"):
        problems.append("unverified_favi_category")
    if channel == "favi" and market in ("GR", "RO") and row.get("color_option_index") \
            and not row.get("verified_variant_color"):
        problems.append("unverified_" + ("greek" if market == "GR" else "romanian") + "_variant_color")
    # The current catalog query uses the base product language. For non-BG
    # publishing require positive evidence of localized copy/URL.
    if market != "BG":
        expected_lang = MARKETS[market]["language"]
        if row.get("verified_locale") != expected_lang:
            problems.append("unverified_localized_copy")
        if not row.get("verified_market_url"):
            problems.append("unverified_market_url")
    return sorted(set(problems))

def audit(rows, market, channel):
    reasons = Counter()
    passed = 0
    processed = 0
    seen = set()
    for row in rows:
        processed += 1
        key = str(row.get("id") or "")
        issues = check_product(row, market, channel)
        if not key or key in seen:
            issues.append("duplicate_or_missing_id")
        if key:
            seen.add(key)
        if issues:
            for issue in set(issues):
                reasons[issue] += 1
        else:
            passed += 1
    return {
        "market": market, "channel": channel,
        "checked": processed, "eligible": passed,
        "excluded": processed - passed,
        "issues": dict(sorted(reasons.items())),
        "publish_ready": processed > 0 and passed > 0 and not reasons,
        "published": False,
    }
