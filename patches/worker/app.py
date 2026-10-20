from __future__ import annotations
from datetime import datetime
from pathlib import Path
import os, subprocess, sys, threading
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from job_store import STORE
from report_store import snapshot, save_reports
from task_registry import TASKS, TASK_ALIASES
from logistics.logistics import build_logistics_report

BASE=Path(__file__).resolve().parent
EASYREA_DIR=BASE/"easyrea"
TOKEN=os.environ.get("HUB_WORKER_TOKEN","")
app=FastAPI(title="Homesector Hub Worker",version="0.1.0")

def auth(authorization: str | None):
    if not TOKEN: raise HTTPException(503,"HUB_WORKER_TOKEN is not configured")
    if authorization != f"Bearer {TOKEN}": raise HTTPException(401,"Unauthorized")

def config_from_env():
    keys=["EASYREA_LOGIN","EASYREA_PASSWORD","SHOPIFY_STORE","SHOPIFY_CLIENT_ID","SHOPIFY_CLIENT_SECRET","SHOPIFY_LOCATION_ID","ANTHROPIC_API_KEY","SPEEDY_USERNAME","SPEEDY_PASSWORD","ECONT_USERNAME","ECONT_PASSWORD","SAMEDAY_USERNAME","SAMEDAY_PASSWORD"]
    return {k:os.environ.get(k,"") for k in keys}

class RunRequest(BaseModel):
    task: str
    mode: str = Field(default="dry", pattern="^(dry|real)$")
    batch_size: int = Field(default=500, ge=1, le=10000)
    batch_number: int = Field(default=1, ge=1, le=10000)
    ai_provider: str = Field(default="auto", pattern="^(auto|claude|openai)$")
    ai_preview: bool = False
    refresh_catalog: bool = False
    repair_product_ids: list[str] = Field(default_factory=list,max_length=100)

class LogisticsRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)

@app.get("/health")
def health(authorization: str | None = Header(default=None)):
    auth(authorization); return {"ok":True,"tasks":len(TASKS),"stock_sync_version":2,"reports_version":1,"import_version":5,"order_skus_version":1,"image_jobs_version":2,"ai_available":{"claude":bool(os.environ.get("ANTHROPIC_API_KEY")),"openai":bool(os.environ.get("OPENAI_API_KEY"))},"time":datetime.now().astimezone().isoformat(timespec="seconds")}

@app.get("/jobs")
def jobs(authorization: str | None = Header(default=None)):
    auth(authorization); return {"jobs":STORE.list()}

@app.get("/jobs/{job_id}")
def job(job_id:str, authorization: str | None = Header(default=None)):
    auth(authorization); j=STORE.get(job_id)
    if not j: raise HTTPException(404,"Job not found")
    return {"job":j.to_dict()}

@app.post("/jobs/run")
def run_job(req:RunRequest, authorization: str | None = Header(default=None)):
    auth(authorization)
    req.task = TASK_ALIASES.get(req.task, req.task)
    if req.task not in TASKS: raise HTTPException(400,"Unknown task")
    if req.repair_product_ids and (req.task!='import_products.py' or any(not __import__('re').fullmatch(r'gid://shopify/Product/[0-9]+',i) for i in req.repair_product_ids)):raise HTTPException(400,'Невалидни продуктови ID за обновяване')
    meta=TASKS[req.task]
    if req.task=="import_products.py" and (req.mode=="real" or req.ai_preview):
        provider=req.ai_provider if req.ai_provider!="auto" else os.environ.get("PRODUCT_AI_PROVIDER","claude").lower()
        if provider=="auto":provider="claude" if os.environ.get("ANTHROPIC_API_KEY") else "openai"
        key="ANTHROPIC_API_KEY" if provider=="claude" else "OPENAI_API_KEY"
        if provider not in ("claude","openai") or not os.environ.get(key):raise HTTPException(503,f"Липсва {key} в Render Worker за избрания AI доставчик")
    job=STORE.create_if_idle(req.task)
    if job is None: raise HTTPException(409,"Тази задача вече се изпълнява")
    def worker():
        STORE.mutate(job.id,status="running",started_at=datetime.now().astimezone().isoformat(timespec="seconds"))
        args=[sys.executable,str(EASYREA_DIR/req.task)]
        if meta["dry_run"]: args.append("--dry-run" if req.mode=="dry" else "--real-run")
        if meta["batch"]: args += ["--batch-size",str(req.batch_size),"--batch-number",str(req.batch_number)]
        env=os.environ.copy(); env["PYTHONUNBUFFERED"]="1"
        env["IMPORT_REPAIR_IDS"]=__import__("json").dumps(req.repair_product_ids)
        env["IMPORT_AI_PROVIDER"]=req.ai_provider
        env["IMPORT_AI_PREVIEW"]="1" if req.mode=="dry" and req.ai_preview else "0"
        env["IMPORT_REFRESH_CATALOG"]="1" if req.refresh_catalog else "0"
        report_dir=BASE/"reports"/job.id
        report_dir.mkdir(parents=True,exist_ok=True)
        env["HUB_REPORT_DIR"]=str(report_dir)
        before=snapshot(report_dir)
        try:
            p=subprocess.Popen(args,cwd=str(EASYREA_DIR),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            chunks=[]
            assert p.stdout is not None
            for line in p.stdout:
                chunks.append(line)
                STORE.mutate(job.id,log="".join(chunks)[-100000:])
            rc=p.wait()
            status="success" if rc==0 else "failed"
            try:
                STORE.mutate(job.id,reports=save_reports(report_dir,before,job.id,req.task,req.mode,status))
            except Exception as e:
                STORE.mutate(job.id,report_error=str(e))
            STORE.mutate(job.id,status=status,return_code=rc,finished_at=datetime.now().astimezone().isoformat(timespec="seconds"))
        except Exception as e:
            STORE.mutate(job.id,status="failed",log=f"{type(e).__name__}: {e}",finished_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    threading.Thread(target=worker,daemon=True).start()
    return {"job":job.to_dict()}

@app.post("/logistics/report")
def logistics(req:LogisticsRequest, authorization: str | None = Header(default=None)):
    auth(authorization); return build_logistics_report(config_from_env(),days=req.days)


# Durable image jobs are separate from the legacy in-memory subprocess jobs.
from image_jobs import IMAGE_JOBS, Conflict
from fastapi.responses import Response

class ImageRunRequest(BaseModel):
    mode: str = Field(default="dry", pattern="^(dry|real)$")
    limit: int = Field(default=100, ge=1, le=5000)
    collection_id: str = Field(default="", pattern="^([0-9]+)?$")

@app.on_event("startup")
def recover_image_jobs():
    # The feed-only staging service must never run the live image repair queue.
    if os.environ.get("RENDER_SERVICE_NAME") == "homesector-worker-feed-staging":
        return
    IMAGE_JOBS.wake()

@app.on_event("shutdown")
def stop_image_jobs():
    IMAGE_JOBS.shutdown.set()

@app.get("/image-jobs")
def image_job_status(authorization: str | None = Header(default=None)):
    auth(authorization)
    try: return {"job": IMAGE_JOBS.status()}
    except Exception: raise HTTPException(503,"Постоянното хранилище за задачата е недостъпно")

@app.post("/image-jobs")
def image_job_start(req: ImageRunRequest, authorization: str | None = Header(default=None)):
    auth(authorization)
    try: return {"job": IMAGE_JOBS.start(req.mode, req.limit, req.collection_id)}
    except Conflict as exc: raise HTTPException(409,str(exc))
    except ValueError as exc: raise HTTPException(400,str(exc))
    except Exception: raise HTTPException(503,"Не може да се запише задачата. Проверете хранилището.")

@app.post("/image-jobs/{action}")
def image_job_control(action: str, authorization: str | None = Header(default=None)):
    auth(authorization)
    try: return {"job": IMAGE_JOBS.control(action)}
    except Conflict as exc: raise HTTPException(409,str(exc))
    except ValueError as exc: raise HTTPException(400,str(exc))
    except Exception: raise HTTPException(503,"Не може да се запази състоянието")

@app.get("/image-jobs/report")
def image_job_report(authorization: str | None = Header(default=None)):
    auth(authorization)
    return Response(IMAGE_JOBS.report(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=product-images.csv"})

from feeds.api import router as feeds_router
app.include_router(feeds_router)

# Feed-only staging: one read-only Shopify connectivity check during startup.
# Log only status and error class, never tokens or catalog content.
@app.on_event("startup")
def probe_feed_shopify_staging():
    if os.environ.get("RENDER_SERVICE_NAME") != "homesector-worker-feed-staging":
        return
    def probe():
        stage = "credentials"
        try:
            from feeds.shopify_auth import get_admin_token
            from feeds.markets_catalog import read_markets_catalog
            store = os.environ.get("SHOPIFY_STORE", "").strip()
            if not store or not store.endswith(".myshopify.com"):
                print("[feeds] Shopify diagnostic: STORE_HOST_MISSING_OR_INVALID", flush=True)
                return
            if not (os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN") or
                    (os.environ.get("SHOPIFY_CLIENT_ID") and os.environ.get("SHOPIFY_CLIENT_SECRET"))):
                print("[feeds] Shopify diagnostic: ACCESS_CREDENTIALS_MISSING", flush=True)
                return
            access_token = get_admin_token(store)
            # Test product reads and country-specific fields separately without logging sensitive values.
            import requests as _requests
            endpoint = f"https://{store}/admin/api/2026-07/graphql.json"
            checks = (
                ("PRODUCTS", "{ products(first: 1) { nodes { id title } } }"),
                ("MARKET_PUBLICATION", "{ products(first: 1) { nodes { id publishedInContext(context: {country: BG}) } } }"),
                ("MARKET_PRICING", "{ products(first: 1) { nodes { variants(first: 1) { nodes { contextualPricing(context: {country: BG}) { price { amount currencyCode } } } } } } }"),
                ("INVENTORY", "{ products(first: 1) { nodes { variants(first: 1) { nodes { inventoryQuantity } } } } }"),
            )
            for label, query in checks:
                check_response = _requests.post(
                    endpoint, headers={"X-Shopify-Access-Token": access_token},
                    json={"query": query}, timeout=20)
                check_response.raise_for_status()
                data = check_response.json()
                denied = bool(data.get("errors")) or not data.get("data", {}).get("products")
                print(f"[feeds] Shopify scope probe {label}: {'DENIED' if denied else 'OK'}", flush=True)
            stage = "catalog_query"
            iterator = read_markets_catalog(store=store, max_pages=1)
            first = next(iterator, None)
            print("[feeds] Shopify diagnostic: CATALOG_OK" if first else "[feeds] Shopify diagnostic: CATALOG_EMPTY", flush=True)
        except Exception as exc:
            import requests
            category = "UNEXPECTED_ERROR"
            if isinstance(exc, requests.HTTPError):
                code = exc.response.status_code if exc.response is not None else 0
                category = f"SHOPIFY_HTTP_{code}"
            elif isinstance(exc, requests.Timeout):
                category = "SHOPIFY_TIMEOUT"
            elif isinstance(exc, RuntimeError):
                category = (str(exc) if str(exc) in {
                    "SHOPIFY_GRAPHQL_QUERY_COST", "SHOPIFY_GRAPHQL_ACCESS_DENIED",
                    "SHOPIFY_GRAPHQL_SCHEMA_MISMATCH", "SHOPIFY_GRAPHQL_REJECTED"}
                    else ("CATALOG_GRAPHQL_REJECTED" if stage == "catalog_query"
                          else "TOKEN_EXCHANGE_FAILED"))
            elif isinstance(exc, ValueError):
                category = "CONFIG_VALIDATION_ERROR"
            print(f"[feeds] Shopify diagnostic: {stage.upper()}_{category}", flush=True)
    threading.Thread(target=probe, daemon=True, name="feed-staging-probe").start()
