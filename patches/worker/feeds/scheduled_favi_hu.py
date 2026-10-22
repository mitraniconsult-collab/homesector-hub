"""Restartable HU preview generations in the BG worker's idle windows."""
import json
import os
import time
import uuid
from pathlib import Path

from .scheduled_favi_gr import (MAX_SCAN_AGE_SECONDS, completed_source_expired,
                                save, source_is_fresh)


def tick(mount, should_stop=lambda: False, deadline=None):
    root = Path(mount).resolve()
    if os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes" or not os.path.ismount(root):
        raise RuntimeError("Confirmed mounted feed storage required")
    path = root / "favi-hu-schedule.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    now = time.time()
    deadline = float("inf") if deadline is None else deadline
    if now < state.get("retry_at", 0):
        return {"status": "retry_wait", "retry_at": state["retry_at"]}
    if not state.get("generation"):
        receipt = state.get("receipt") or {}
        if (os.getenv("FEED_FAVI_HU_PREVIEW_PUBLISH") == "yes"
                and receipt.get("status") in ("private_complete", "partial_preview_uploaded")
                and receipt.get("report_version") != 2
                and state.get("last_generation")):
            folder = root / "favi-hu-runs" / state["last_generation"] / "favi-hu-source"
            report = json.loads((folder / "favi-hu-report.json").read_text(encoding="utf-8"))
            if not report.get("private_audit_passed") or not source_is_fresh(
                    state["started_at"], report, now):
                return {"status": "private_preview_expired",
                        "generation": state["last_generation"]}
            from .favi_hu_delivery import publish_preview
            published = publish_preview(root, folder)
            state.update(receipt=published, last_success_at=time.time(),
                         last_items=published["items"])
            save(path, state)
            return {**published, "generation": state["last_generation"]}
        if now < state.get("next_run_at", 0):
            return {"status": "waiting", "next_run_at": state["next_run_at"]}
        state.update(generation=uuid.uuid4().hex, started_at=now)
        save(path, state)
    generation = state["generation"]
    if not isinstance(generation, str) or len(generation) != 32 or any(
            c not in "0123456789abcdef" for c in generation):
        raise ValueError("Invalid HU generation ID")
    if should_stop() or time.time() >= deadline:
        return {"status": "yielded", "generation": generation}
    folder = root / "favi-hu-runs" / generation / "favi-hu-source"
    if completed_source_expired(folder, time.time()):
        state.update(generation=None, rejected_generation=generation,
                     last_error="StaleSource", next_run_at=time.time() + 300)
        save(path, state)
        return {"status": "stale_source_restarting", "generation": generation,
                "next_run_at": state["next_run_at"]}
    try:
        from .favi_hu_catalog import execute
        report = execute(batch_limit=int(os.getenv("FEED_HU_PAGE_LIMIT", "100")),
                         root=root, source_folder=folder, deadline=deadline,
                         should_stop=should_stop)
        state.update(progress={"status": report["status"],
                               "source_products": report.get("source_products")},
                     updated_at=now)
        save(path, state)
        if (report["status"] in ("incomplete", "yielded") or should_stop()
                or time.time() >= deadline):
            status = "yielded" if should_stop() or time.time() >= deadline else report["status"]
            return {"status": status, "stage": report.get("stage"),
                    "generation": generation,
                    "source_products": report.get("source_products")}
        if not report.get("source_complete"):
            raise RuntimeError("Incomplete HU source generation")
        if not source_is_fresh(state["started_at"], report, time.time()):
            state.update(generation=None, rejected_generation=generation,
                         last_error="StaleGeneration", next_run_at=time.time() + 300)
            save(path, state)
            return {"status": "stale_generation_rejected", "generation": generation}
        if os.getenv("FEED_FAVI_HU_PREVIEW_PUBLISH") == "yes":
            from .favi_hu_delivery import publish_preview
            receipt = publish_preview(root, folder)
        else:
            receipt = {"status": "private_complete", "items": report["xml_items"]}
        state.update(generation=None, last_generation=generation,
                     last_success_at=time.time(), last_items=receipt["items"],
                     next_run_at=time.time() + 86400, last_error=None,
                     receipt=receipt, retry_at=0)
        save(path, state)
        return {**receipt, "generation": generation,
                "sha256": report["sha256"]}
    except Exception as exc:
        state.update(last_error=type(exc).__name__, retry_at=time.time() + 300)
        save(path, state)
        raise
