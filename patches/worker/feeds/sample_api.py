"""Read-only, authenticated first-page feed validation. Not a public feed."""
import os
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from .markets_catalog import read_markets_catalog
from .preview import preview

router = APIRouter(prefix="/feeds", tags=["feeds"])

def authorize(value):
    token = os.environ.get("HUB_WORKER_TOKEN")
    if not token:
        raise HTTPException(503, "Feed authorization unavailable")
    if value != "Bearer " + token:
        raise HTTPException(401, "Unauthorized")

def build_sample():
    try:
        # A single five-product page; never treat as a complete feed.
        catalog = list(read_markets_catalog(max_pages=1))
        result = preview(catalog, "BG", "google")
    except Exception:
        raise HTTPException(502, "Shopify feed preview unavailable")
    return result

@router.get("/google/BG/preview")
def google_bg_preview(authorization: str | None = Header(default=None)):
    authorize(authorization)
    result = build_sample()
    result.pop("xml", None)
    result["sample_only"] = True
    result["published"] = False
    return result

@router.get("/google/BG/sample.xml")
def google_bg_sample_xml(authorization: str | None = Header(default=None)):
    authorize(authorization)
    result = build_sample()
    return Response(content=result["xml"], media_type="application/xml",
                    headers={"Cache-Control": "no-store", "X-Feed-Sample": "true"})
