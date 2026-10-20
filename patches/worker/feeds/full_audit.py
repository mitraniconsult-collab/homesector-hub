"""Staging-only full Google BG catalog audit and unpublished XML build.
No Shopify writes, no Google submissions; artifacts live on ephemeral Render storage.
"""
import json
import os
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from .markets_catalog import read_markets_catalog
from .markets_normalize import normalize_market
from .config import eligible
from .xml_export import generate

router = APIRouter(prefix="/feeds/google/BG", tags=["feeds"])
ROOT = Path(tempfile.gettempdir()) / "homesector-feed-audit"
ROOT.mkdir(parents=True, exist_ok=True)
XML_PATH = ROOT / "google-bg-unpublished.xml"
GUARD = threading.Lock()
STATE = {"status": "idle", "products_scanned": 0, "variants_checked": 0,
         "items_exported": 0, "excluded": {}, "started_at": None,
         "completed_at": None, "error_type": None}

def now():
    return datetime.now(timezone.utc).isoformat()

def authorized(value):
    token = os.environ.get("HUB_WORKER_TOKEN")
    if not token:
        raise HTTPException(503, "Authorization unavailable")
    if value != "Bearer " + token:
        raise HTTPException(401, "Unauthorized")

def state_snapshot():
    with GUARD:
        return dict(STATE)

def run_export():
    reasons = Counter()
    rows = []
    ids = set()
    try:
        for product in read_markets_catalog():
            variants = (product.get("variants") or {}).get("nodes") or []
            with GUARD:
                STATE["products_scanned"] += 1
                STATE["variants_checked"] += len(variants)
                number = STATE["products_scanned"]
            if product.get("status") != "ACTIVE":
                reasons["inactive_products"] += 1
                continue
            if not product.get("published_BG"):
                reasons["not_published_bg"] += 1
                continue
            if not product.get("handle"):
                reasons["missing_handle"] += 1
                continue
            for variant in variants:
                money = ((variant.get("price_BG") or {}).get("price") or {})
                if money.get("currencyCode") != "EUR" or not money.get("amount"):
                    reasons["invalid_bg_price"] += 1
                    continue
                if not (variant.get("image") or product.get("featuredImage")):
                    reasons["missing_image"] += 1
                    continue
                normalized = normalize_market(
                    {**product, "variants": {"nodes": [variant]}}, "BG")
                if not normalized:
                    reasons["normalization_failed"] += 1
                    continue
                row = normalized[0]
                if not eligible(row, "BG"):
                    reasons["not_sellable_or_missing_fields"] += 1
                    continue
                if row["id"] in ids:
                    reasons["duplicate_variant_id"] += 1
                    continue
                ids.add(row["id"])
                rows.append(row)
                if not row.get("gtin"):
                    reasons["missing_gtin_included"] += 1
                if not row.get("description"):
                    reasons["missing_description_included"] += 1
            if number % 100 == 0:
                with GUARD:
                    STATE["items_exported"] = len(rows)
                    STATE["excluded"] = dict(reasons)
                print(f"[feeds] BG full audit progress: products={number} items={len(rows)}", flush=True)
        xml = generate(rows, "BG", "google")
        root = ET.fromstring(xml)
        count = len(root.findall("./channel/item"))
        if count != len(rows):
            raise RuntimeError("Google BG XML item count mismatch")
        temp_path = XML_PATH.with_suffix(".tmp")
        temp_path.write_bytes(xml)
        os.replace(temp_path, XML_PATH)
        with GUARD:
            STATE.update(status="completed", items_exported=count,
                         excluded=dict(reasons), completed_at=now())
        print(f"[feeds] BG full audit COMPLETED: scanned={STATE['products_scanned']} items={count}", flush=True)
    except Exception as exc:
        with GUARD:
            STATE.update(status="failed", excluded=dict(reasons),
                         error_type=type(exc).__name__, completed_at=now())
        print(f"[feeds] BG full audit FAILED: {type(exc).__name__}", flush=True)

def start_once():
    if os.environ.get("RENDER_SERVICE_NAME") != "homesector-worker-feed-staging":
        return False
    with GUARD:
        if STATE["status"] != "idle":
            return False
        STATE.update(status="running", started_at=now())
    threading.Thread(target=run_export, name="google-bg-full-audit", daemon=True).start()
    return True

@router.get("/full-audit")
def full_audit_status(authorization: str | None = Header(default=None)):
    authorized(authorization)
    return {**state_snapshot(), "published_to_google": False,
            "durable_storage": False}

@router.get("/full-audit.xml")
def full_audit_xml(authorization: str | None = Header(default=None)):
    authorized(authorization)
    if state_snapshot()["status"] != "completed" or not XML_PATH.exists():
        raise HTTPException(409, "Audit not completed")
    return Response(XML_PATH.read_bytes(), media_type="application/xml",
                    headers={"Cache-Control": "private, no-store",
                             "X-Unpublished-Feed": "true"})
