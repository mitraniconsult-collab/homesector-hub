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
    repair_product_ids: list[str] = Field(default_factory=list,max_length=100)

class LogisticsRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)

@app.get("/health")
def health(authorization: str | None = Header(default=None)):
    auth(authorization); return {"ok":True,"tasks":len(TASKS),"stock_sync_version":2,"reports_version":1,"import_version":4,"order_skus_version":1,"ai_available":{"claude":bool(os.environ.get("ANTHROPIC_API_KEY")),"openai":bool(os.environ.get("OPENAI_API_KEY"))},"time":datetime.now().astimezone().isoformat(timespec="seconds")}

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
