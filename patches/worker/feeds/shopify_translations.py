"""Read-only batched Shopify translations for the Homesector market feeds.

Returns actual Shopify product translations only. Missing keys remain missing and
are rejected by channel preflight. No translation generation or product writes.
"""
import os
from .shopify_auth import get_admin_token

LOCALES = {"RO": "ro", "GR": "el", "HU": "hu"}
BATCH_SIZE = 5

def translations_query(batch_size):
    if not 1 <= batch_size <= BATCH_SIZE:
        raise ValueError("Unexpected Shopify translation batch size")
    vars_decl = ", ".join(f"$p{i}: ID!" for i in range(batch_size))
    parts = []
    for i in range(batch_size):
        translations = " ".join(
            f'{country.lower()}: translations(locale: "{locale}") {{ key value }}'
            for country, locale in LOCALES.items()
        )
        parts.append(f"p{i}: product(id: $p{i}) {{ id {translations} }}")
    return "query FeedProductTranslations(" + vars_decl + ") { " + " ".join(parts) + " }"

def fetch_translations(product_ids, store=None, token=None, version="2026-07"):
    from .markets_catalog import shopify_post
    store = (store or os.environ.get("SHOPIFY_STORE", "")).strip()
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify store")
    ids = list(dict.fromkeys(product_ids))
    if any(not isinstance(x, str) or not x.startswith("gid://shopify/Product/") for x in ids):
        raise ValueError("Expected Shopify Product IDs")
    if not ids:
        return {}
    token = token or get_admin_token(store)
    url = f"https://{store}/admin/api/{version}/graphql.json"
    result = {}
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start:start + BATCH_SIZE]
        values = {f"p{i}": product_id for i, product_id in enumerate(batch)}
        data = shopify_post(url, token, {
            "query": translations_query(len(batch)), "variables": values})
        if data.get("errors") or not data.get("data"):
            raise RuntimeError("Shopify translations query failed")
        for i, product_id in enumerate(batch):
            product = data["data"].get(f"p{i}")
            if not product or product.get("id") != product_id:
                raise RuntimeError("Shopify translations response incomplete")
            result[product_id] = {
                country: product.get(country.lower()) or []
                for country in LOCALES
            }
    return result


def fetch_variant_translations(variant_ids, market, store=None, token=None,
                               version="2026-07"):
    """Fetch actual Shopify option translations keyed by variant GID."""
    if market not in LOCALES:
        raise ValueError("Unsupported translation locale")
    ids = list(dict.fromkeys(variant_ids))
    if any(not isinstance(x, str) or not x.startswith("gid://shopify/ProductVariant/") for x in ids):
        raise ValueError("Expected Shopify ProductVariant IDs")
    if not ids:
        return {}
    from .markets_catalog import shopify_post
    store = (store or os.environ.get("SHOPIFY_STORE", "")).strip()
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify store")
    token = token or get_admin_token(store)
    url = f"https://{store}/admin/api/{version}/graphql.json"
    result = {}
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start:start + BATCH_SIZE]
        vars_decl = ", ".join(f"$v{i}: ID!" for i in range(len(batch)))
        fields = " ".join(
            f'v{i}: productVariant(id: $v{i}) {{ id translations(locale: "{LOCALES[market]}") {{ key value }} }}'
            for i in range(len(batch)))
        query = f"query FeedVariantTranslations({vars_decl}) {{ {fields} }}"
        values = {f"v{i}": gid for i, gid in enumerate(batch)}
        # shopify_post accepts URL, token, payload; never log returned copy.
        data = shopify_post(url, token, {"query": query, "variables": values})
        if data.get("errors") or not data.get("data"):
            raise RuntimeError("Shopify variant translations query failed")
        for i, gid in enumerate(batch):
            variant = data["data"].get(f"v{i}")
            if not variant or variant.get("id") != gid:
                raise RuntimeError("Shopify variant translation response incomplete")
            result[gid] = variant.get("translations") or []
    return result
