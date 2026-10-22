"""Verify Shopify collection-context landing pages when direct GR URLs fail.

A collection path is used only if Shopify lists the product in that collection
and the public Greek page responds with the same product handle on the GR host.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote, urlparse
import requests
from .favi_gr_rate_limit import storefront_limiter
from .batch_job import post_graphql

QUERY = """
query FeedCollectionPaths($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on Product {
      id handle
      collections(first: 20) { nodes { handle } pageInfo { hasNextPage } }
    }
  }
}
"""


def _candidates(products, missing_ids, store, token):
    selected = {p["id"]: p for p in products if p.get("id") in missing_ids}
    url = f"https://{store}/admin/api/2026-07/graphql.json"
    ids = sorted(selected)
    result = {}
    for start in range(0, len(ids), 10):
        nodes = post_graphql(url, token, QUERY, {"ids": ids[start:start + 10]})["nodes"]
        if start % 100 == 0:
            print(f"[favi-gr-collection-source] checked={start + len(nodes)} total={len(ids)}", flush=True)
        for node in nodes:
            if not node or node.get("id") not in selected:
                continue
            product = selected[node["id"]]
            if node.get("handle") != product.get("handle"):
                continue
            handles = []
            for collection in (node.get("collections") or {}).get("nodes") or []:
                handle = str(collection.get("handle") or "")
                if handle and "/" not in handle and "?" not in handle and "#" not in handle:
                    handles.append(handle)
            # Category collection paths can serve a GR product even when its
            # direct /products/ URL returns 404. They may appear after the
            # first four memberships and after several brand collections.
            generic = {"allproducts", "atmosphera", "5five", "hesperide", "buy3pay2"}
            specific = [h for h in dict.fromkeys(handles) if h.casefold() not in generic]
            specific.sort(key=lambda h: not h.casefold().endswith("-category"))
            result[node["id"]] = (specific or list(dict.fromkeys(handles)))[:2]
    return result


def _check(product, collections):
    handle = str(product.get("handle") or "")
    if not handle or "/" in handle or "?" in handle or "#" in handle:
        return None
    for collection in collections:
        path = "/collections/" + quote(collection, safe="-") + "/products/" + quote(handle, safe="-")
        try:
            response = storefront_limiter.get("https://homesector.gr" + path, timeout=5,
                                    allow_redirects=True,
                                    headers={"User-Agent": "HomesectorFeedVerifier/1.0"})
            final = urlparse(response.url)
            if (response.status_code == 200 and final.scheme == "https"
                    and final.hostname == "homesector.gr"
                    and unquote(final.path).rstrip("/") == unquote(path)
                    and "text/html" in response.headers.get("Content-Type", "").lower()
                    and handle in response.text):
                return "https://homesector.gr" + path
        except requests.RequestException:
            continue
    return None


def verify_collection_urls(products, already_verified, store, token, workers=16):
    if not 1 <= workers <= 16:
        raise ValueError("Invalid URL verification concurrency")
    missing = {p["id"]: p for p in products if p.get("id") not in already_verified}
    if not missing:
        return {}, {"checked": 0, "verified": 0}
    candidates = _candidates(products, set(missing), store, token)
    verified = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_check, missing[pid], handles): pid
                   for pid, handles in candidates.items() if handles}
        for future in as_completed(futures):
            path = future.result()
            if path:
                verified[futures[future]] = path
    return verified, {"checked": len(futures), "verified": len(verified),
                      "without_collection": len(missing) - len(futures)}

