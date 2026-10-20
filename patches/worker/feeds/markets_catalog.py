"""Shopify Markets-aware read-only product catalog query.

Uses Shopify's country-specific publication and contextualPricing fields.
Does not assume all countries share the store's base prices.
"""
import os
import requests
from .shopify_auth import get_admin_token

COUNTRIES = ("BG", "RO", "GR", "HU")

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
      products(first: 50, after: $cursor, sortKey: ID) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id title handle descriptionHtml status vendor productType
          featuredImage { url }
          """ + publication + """
          variants(first: 100) {
            pageInfo { hasNextPage }
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

def read_markets_catalog(store=None, token=None, version="2026-07", max_pages=1000):
    store = (store or os.environ.get("SHOPIFY_STORE", "")).strip()
    token = token or get_admin_token(store)
    if not store.endswith(".myshopify.com") or not token:
        raise ValueError("Valid SHOPIFY_STORE and SHOPIFY_ADMIN_ACCESS_TOKEN required")
    url = f"https://{store}/admin/api/{version}/graphql.json"
    cursor = None
    for _ in range(max_pages):
        response = requests.post(url, headers={"X-Shopify-Access-Token": token},
                                 json={"query": catalog_query(), "variables": {"cursor": cursor}}, timeout=60)
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError("Shopify Markets GraphQL query failed")
        page = payload["data"]["products"]
        for product in page["nodes"]:
            if product["variants"]["pageInfo"]["hasNextPage"]:
                raise RuntimeError("Product has over 100 variants: pagination required before feed export")
            yield product
        if not page["pageInfo"]["hasNextPage"]:
            return
        cursor = page["pageInfo"]["endCursor"]
        if not cursor:
            raise RuntimeError("Missing pagination cursor")
    raise RuntimeError("Shopify catalog pagination limit reached")
