"""Isolated Homesector feed background-worker entrypoint.

Use with Render Background Worker (paid) and an attached persistent disk.
Do not run under Uvicorn or on an ephemeral Render Free web service.
No data is published to Google/Meta/FAVI/Biano by this runner.
"""
import fcntl
import json
import os
import signal
import sys
import time
from pathlib import Path
from .batch_job import execute
from .snapshot_audit import audit_snapshots

_stop = False

def request_stop(_signum, _frame):
    global _stop
    _stop = True

def run():
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    # Disabled staging mode runs without Shopify credentials or feed writes.
    if os.getenv("FEED_BG_JOB_ENABLED") != "yes":
        mount = os.getenv("FEED_DURABLE_PATH", "").strip()
        disk_exists = bool(mount and Path(mount).is_dir())
        disk_is_mount = bool(disk_exists and os.path.ismount(mount))
        print(f"[feeds-job] SAFE_IDLE export_disabled=true disk_path_present={disk_exists} disk_is_mount={disk_is_mount}", flush=True)
        while not _stop:
            time.sleep(5)
        return
    if os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes":
        raise RuntimeError("Durable volume is not confirmed")
    mount = os.getenv("FEED_DURABLE_PATH", "").strip()
    if not mount or not Path(mount).is_dir() or not os.path.ismount(mount):
        raise RuntimeError("Persistent feed mount is missing or not mounted")
    page_limit = int(os.getenv("FEED_JOB_PAGE_LIMIT", "25"))
    if page_limit < 1 or page_limit > 1000:
        raise ValueError("Invalid page limit")
    interval = int(os.getenv("FEED_RUN_INTERVAL_SECONDS", "30"))
    if not 5 <= interval <= 3600:
        raise ValueError("Invalid batch interval")
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    lockfile = Path(mount) / "google-bg-single-writer.lock"
    with lockfile.open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another feed export already owns the persistent journal")
        def log_snapshot_quality():
            report = audit_snapshots(mount)
            print("[feeds-quality] " + json.dumps(report, sort_keys=True), flush=True)

        log_snapshot_quality()
        if os.getenv("FEED_FAVI_BG_PREVIEW") == "yes":
            from .favi_bg_preview import create_preview
            try:
                report = create_preview(mount)
                log_snapshot_quality()
                print("[favi-bg-preview] " + json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
            except Exception as exc:
                print(f"[favi-bg-preview] FAILED type={type(exc).__name__} cause={str(exc)[:120]}", flush=True)
                raise
            while not _stop:
                time.sleep(5)
            return
        if os.getenv("FEED_FAVI_SHOPIFY_CATEGORY_SCAN") == "yes":
            from .favi_shopify_category_scan import scan
            while not _stop:
                try:
                    report = scan(mount, page_limit=100)
                    print("[favi-shopify] " + json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
                except Exception as exc:
                    print(f"[favi-shopify] FAILED type={type(exc).__name__} cause={str(exc)[:120]}", flush=True)
                    raise
                if report["status"] == "complete":
                    while not _stop:
                        time.sleep(10)
                    return
                time.sleep(5)
            return
        if os.getenv("FEED_FAVI_CATEGORY_AUDIT") == "yes":
            from .favi_category_audit import audit
            try:
                report = audit(mount)
                # Do not print product names or raw feed identifiers into logs.
                public_report = {k: v for k, v in report.items()
                                 if k not in ("top_shopify_product_types",
                                              "candidate_mapping_samples")}
                print("[favi-category] " + json.dumps(public_report, sort_keys=True), flush=True)
                print("[favi-category] top_types=" + json.dumps(report["top_shopify_product_types"][:20], ensure_ascii=False), flush=True)
                print("[favi-category] report saved to durable disk; nothing published", flush=True)
            except Exception as exc:
                print(f"[favi-category] FAILED type={type(exc).__name__} cause={str(exc)[:180]}", flush=True)
                raise
            while not _stop:
                time.sleep(5)
            return
        reference_url = os.getenv("FEED_REFERENCE_AUDIT_URL", "").strip()
        if reference_url:
            from .favi_reference_audit import compare
            try:
                report = compare(reference_url, mount)
                print("[favi-reference] " + json.dumps(report, sort_keys=True), flush=True)
            except Exception as exc:
                print(f"[favi-reference] FAILED type={type(exc).__name__}", flush=True)
                raise
            print("[favi-reference] private report saved; no feeds published", flush=True)
            while not _stop:
                time.sleep(5)
            return
        print("[feeds-job] worker STARTED unpublished read-only BG export", flush=True)
        while not _stop:
            try:
                result = execute(batch_limit=page_limit)
            except Exception as exc:
                # Never log env vars or credentials.
                print(f"[feeds-job] FAILED type={type(exc).__name__}", flush=True)
                raise
            print("[feeds-job] " + json.dumps(result, sort_keys=True), flush=True)
            if os.getenv("FEED_CANARY_ONLY") == "yes":
                print("[feeds-job] CANARY_COMPLETE export_unpublished=true; waiting for manual approval", flush=True)
                while not _stop:
                    time.sleep(5)
                break
            if result["status"] == "completed":
                log_snapshot_quality()
                print("[feeds-job] AUDIT COMPLETE; parked until explicitly configured to regenerate", flush=True)
                while not _stop:
                    time.sleep(30)
                break
            slept = 0
            while slept < interval and not _stop:
                time.sleep(min(5, interval - slept))
                slept += min(5, interval - slept)
        print("[feeds-job] stopped cleanly", flush=True)

if __name__ == "__main__":
    run()
