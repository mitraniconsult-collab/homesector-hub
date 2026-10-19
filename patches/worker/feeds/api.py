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
