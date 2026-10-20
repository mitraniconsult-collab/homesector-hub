"""Shopify Markets-aware read-only product catalog query.

Uses Shopify's country-specific publication and contextualPricing fields.
Does not assume all countries share the store's base prices.
"""
import os
import requests
import time
from .shopify_auth import get_admin_token

COUNTRIES = ("BG", "RO", "GR", "HU")

def shopify_post(url, token, payload):
    """Bounded retries for temporary Shopify API failures."""
    for attempt in range(6):
        try:
            response = requests.post(
                url, headers={"X-Shopify-Access-Token": token},
                json=payload, timeout=60)
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < 5:
                    delay = min(30, 2 ** attempt)
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = min(60, max(delay, float(retry_after)))
                        except ValueError:
                            pass
                    time.sleep(delay)
                    continue
            response.raise_for_status()
            return response.json()
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 5:
                raise
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError("Shopify retry limit reached")


def catalog_query():
    publication = "\n".join(
        f"published_{country}: publishedInContext(context: {{country: {country}}})"
        for country in COUNTRIES
    )
    pricing = "\n".join(
        f"price_{country}: contextualPricing(context: {{country: {country}}}) "
        "{ price { amount currencyCode } }"
        for country in COUNTRIES
    )
    return """
    query FeedMarkets($cursor: String) {
      products(first: 5, after: $cursor, sortKey: ID) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id title handle descriptionHtml status vendor productType
          featuredImage { url }
          """ + publication + """
          variants(first: 25) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id sku barcode inventoryQuantity inventoryPolicy
              image { url }
              """ + pricing + """
            }
          }
        }
      }
    }
    """

def read_markets_catalog(store=None, token=None, version="2026-07", max_pages=10000):
    store = (store or os.environ.get("SHOPIFY_STORE", "")).strip()
    token = token or get_admin_token(store)
    if not store.endswith(".myshopify.com") or not token:
        raise ValueError("Valid SHOPIFY_STORE and SHOPIFY_ADMIN_ACCESS_TOKEN required")
    url = f"https://{store}/admin/api/{version}/graphql.json"
    cursor = None
    for _ in range(max_pages):
        payload = shopify_post(url, token, {"query": catalog_query(), "variables": {"cursor": cursor}})
        if payload.get("errors"):
            codes = {str((item.get("extensions") or {}).get("code", "")).upper()
                     for item in payload["errors"] if isinstance(item, dict)}
            descriptions = " ".join(str(item.get("message", "")).lower()
                                    for item in payload["errors"] if isinstance(item, dict))
            if "MAX_COST_EXCEEDED" in codes or "cost" in descriptions and "exceed" in descriptions:
                raise RuntimeError("SHOPIFY_GRAPHQL_QUERY_COST")
            if "ACCESS_DENIED" in codes or "access denied" in descriptions:
                raise RuntimeError("SHOPIFY_GRAPHQL_ACCESS_DENIED")
            if "undefinedfield" in descriptions or "doesn't exist" in descriptions:
                raise RuntimeError("SHOPIFY_GRAPHQL_SCHEMA_MISMATCH")
            raise RuntimeError("SHOPIFY_GRAPHQL_REJECTED")
        page = payload["data"]["products"]
        for product in page["nodes"]:
            if product["variants"]["pageInfo"]["hasNextPage"]:
                product["variants"]["nodes"].extend(
                    read_remaining_variants(url, token, product["id"],
                                            product["variants"]["pageInfo"]["endCursor"]))
                product["variants"]["pageInfo"]["hasNextPage"] = False
            yield product
        if not page["pageInfo"]["hasNextPage"]:
            return
        cursor = page["pageInfo"]["endCursor"]
        if not cursor:
            raise RuntimeError("Missing pagination cursor")
    raise RuntimeError("Shopify catalog pagination limit reached")

def read_remaining_variants(url, token, product_id, cursor):
    """Page through every variant; fail rather than silently drop any."""
    if not cursor:
        raise RuntimeError("Missing variant cursor")
    pricing = "\n".join(
        f"price_{country}: contextualPricing(context: {{country: {country}}}) "
        "{ price { amount currencyCode } }" for country in COUNTRIES
    )
    query = """
    query FeedVariants($productId: ID!, $cursor: String) {
      product(id: $productId) {
        variants(first: 25, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            id sku barcode inventoryQuantity inventoryPolicy
            image { url }
            """ + pricing + """
          }
        }
      }
    }
    """
    all_variants = []
    for _ in range(1000):
        payload = shopify_post(url, token, {"query": query, "variables": {"productId": product_id, "cursor": cursor}})
        if payload.get("errors") or not (payload.get("data") or {}).get("product"):
            raise RuntimeError("Shopify variant pagination query failed")
        page = payload["data"]["product"]["variants"]
        all_variants.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return all_variants
        new_cursor = page["pageInfo"]["endCursor"]
        if not new_cursor or new_cursor == cursor:
            raise RuntimeError("Invalid Shopify variant pagination cursor")
        cursor = new_cursor
    raise RuntimeError("Shopify variant pagination limit reached")
