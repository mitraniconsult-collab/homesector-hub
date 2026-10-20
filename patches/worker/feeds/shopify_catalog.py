"""Shopify Admin GraphQL catalog reader for feed staging (read-only).

Requires SHOPIFY_STORE and SHOPIFY_ADMIN_ACCESS_TOKEN. No secrets are logged.
The result is raw Shopify data; market-specific pricing/publication must be
resolved before passing products to xml_export.generate().
"""
import os
import requests

QUERY = """
query FeedCatalog($cursor: String) {
  products(first: 100, after: $cursor, sortKey: ID) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id title handle status vendor productType
      featuredImage { url }
      images(first: 10) { nodes { url } }
      variants(first: 100) {
        nodes { id sku barcode price inventoryQuantity
          inventoryPolicy selectedOptions { name value }
          image { url }
        }
      }
    }
  }
}
"""

def fetch_catalog(store=None, token=None, api_version="2026-07", max_pages=500):
    store = (store or os.environ.get("SHOPIFY_STORE", "")).strip()
    token = token or os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN", "")
    if not store or not token:
        raise RuntimeError("Missing Shopify store or Admin API access token")
    if not store.endswith(".myshopify.com"):
        raise ValueError("SHOPIFY_STORE must be a myshopify.com hostname")
    endpoint = f"https://{store}/admin/api/{api_version}/graphql.json"
    cursor = None
    for _ in range(max_pages):
        response = requests.post(
            endpoint,
            headers={"X-Shopify-Access-Token": token},
            json={"query": QUERY, "variables": {"cursor": cursor}},
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            raise RuntimeError("Shopify GraphQL query failed")
        connection = body["data"]["products"]
        yield from connection["nodes"]
        if not connection["pageInfo"]["hasNextPage"]:
            return
        cursor = connection["pageInfo"]["endCursor"]
        if not cursor:
            raise RuntimeError("Missing Shopify pagination cursor")
    raise RuntimeError("Catalog exceeds configured pagination safety limit")
