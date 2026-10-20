"""Authenticated feed status API. No fabricated live URLs or counts."""
from fastapi import APIRouter, Header, HTTPException
import os
import secrets
from .targets import targets

router = APIRouter(prefix="/feeds", tags=["feeds"])

@router.get("/status")
def status(authorization: str | None = Header(default=None)):
    token = os.environ.get("HUB_WORKER_TOKEN")
    if not token:
        raise HTTPException(503, "Worker authentication not configured")
    if not secrets.compare_digest(authorization or "", "Bearer " + token):
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
            "feeds_published": False, "legacy_api_audit_enabled": os.getenv("FEED_LEGACY_API_AUDIT_ENABLED") == "yes",
            "snapshot_report_available": _report_available()}

@router.get("/catalog-config")
def catalog_config(authorization: str | None = Header(default=None)):
    """Read-only credential readiness, never return actual secrets."""
    token = os.environ.get("HUB_WORKER_TOKEN")
    if not token:
        raise HTTPException(503, "Worker authentication not configured")
    if not secrets.compare_digest(authorization or "", "Bearer " + token):
        raise HTTPException(401, "Unauthorized")
    store = os.environ.get("SHOPIFY_STORE", "").strip()
    oauth_ready = bool(os.environ.get("SHOPIFY_CLIENT_ID")) and bool(os.environ.get("SHOPIFY_CLIENT_SECRET"))
    return {
        "shopify_oauth_credentials_configured": oauth_ready,
        "shopify_store_configured": store.endswith(".myshopify.com"),
        "shopify_admin_token_configured": bool(os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN")),
        "catalog_ready": store.endswith(".myshopify.com")
                         and (bool(os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN")) or oauth_ready),
        "read_only": True,
    }


def _report_available():
    from .snapshot_audit import report_path
    path = report_path()
    return path is not None and path.is_file()


@router.get("/diagnostics")
def diagnostics(authorization: str | None = Header(default=None)):
    """Read-only persisted diagnostics; never imply a separate disk is shared."""
    token = os.environ.get("HUB_WORKER_TOKEN")
    if not token:
        raise HTTPException(503, "Worker authentication not configured")
    if not secrets.compare_digest(authorization or "", "Bearer " + token):
        raise HTTPException(401, "Unauthorized")
    from .snapshot_audit import read_report
    report = read_report()
    if report is None:
        raise HTTPException(503, "Durable snapshot report unavailable on this service")
    return report
