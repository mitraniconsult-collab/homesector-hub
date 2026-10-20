"""Shopify Admin API credentials for internal Homesector app (read-only usage)."""
import os
import time
import threading
import requests

_cached = {"token": None, "expires_at": 0.0}
_lock = threading.Lock()


def get_admin_token(store):
    static_token = os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN", "").strip()
    if static_token:
        return static_token
    client_id = os.environ.get("SHOPIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SHOPIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Shopify credentials not configured")
    if not store or not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify store host")
    with _lock:
        if _cached["token"] and _cached["expires_at"] > time.time() + 300:
            return _cached["token"]
        response = requests.post(
            f"https://{store}/admin/oauth/access_token",
            data={"grant_type": "client_credentials",
                  "client_id": client_id, "client_secret": client_secret},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Shopify access token response was empty")
        _cached["token"] = token
        _cached["expires_at"] = time.time() + int(payload.get("expires_in", 86400))
        return token
