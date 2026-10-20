"""Authenticated feed status API. No fabricated live URLs or counts."""
from fastapi import APIRouter, Header, HTTPException
import os
from .targets import targets

router = APIRouter(prefix="/feeds", tags=["feeds"])

@router.get("/status")
def status(authorization: str | None = Header(default=None)):
    token = os.environ.get("HUB_WORKER_TOKEN")
    if not token:
        raise HTTPException(503, "Worker authentication not configured")
    if authorization != "Bearer " + token:
        raise HTTPException(401, "Unauthorized")
    return {"feeds": [
        {"channel": channel, "market": market, "status": "not_published",
         "product_count": None, "last_updated": None, "xml_url": None}
        for channel, market in targets()
    ]}

@router.get("/check")
def check():
    """Safe public smoke test: no credentials, product data, or private feed URLs."""
    return {"ok": True, "module": "feed-manager", "configured_feeds": len(targets()),
            "api_auth_configured": bool(os.environ.get("HUB_WORKER_TOKEN")),
            "feeds_published": False}

@router.get("/catalog-config")
def catalog_config(authorization: str | None = Header(default=None)):
    """Read-only credential readiness, never return actual secrets."""
    token = os.environ.get("HUB_WORKER_TOKEN")
    if not token:
        raise HTTPException(503, "Worker authentication not configured")
    if authorization != "Bearer " + token:
        raise HTTPException(401, "Unauthorized")
    store = os.environ.get("SHOPIFY_STORE", "").strip()
    return {
        "shopify_store_configured": store.endswith(".myshopify.com"),
        "shopify_admin_token_configured": bool(os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN")),
        "catalog_ready": store.endswith(".myshopify.com")
                         and bool(os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN")),
        "read_only": True,
    }
