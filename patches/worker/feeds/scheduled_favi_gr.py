"""Daily checkpointed Greek catalog generations on the confirmed feed disk.

Only a complete, recent generation can replace the partial preview pointer.
The previous public preview and its source journal stay untouched on errors.
"""
import json
import os
import shutil
import time
import uuid
from pathlib import Path

MAX_SCAN_AGE_SECONDS = 6 * 3600


def save(path, state):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        json.dump(state, fh)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, path)


def _read_state(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _clean_runs(root, active=None):
    runs = root / "favi-gr-runs"
    if not runs.exists():
        return
    for old in sorted(runs.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[3:]:
        if old.is_dir() and not old.is_symlink() and old.name != active:
            shutil.rmtree(old)


def tick(mount, should_stop=lambda: False, now=None, deadline=None):
    root = Path(mount).resolve()
    if os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes" or not os.path.ismount(root):
        raise RuntimeError("Confirmed mounted feed storage required")
    interval = int(os.getenv("FEED_FAVI_GR_REGENERATE_SECONDS", "86400"))
    if not 3600 <= interval <= 604800:
        raise ValueError("GR regeneration interval must be 3600..604800 seconds")
    page_limit = int(os.getenv("FEED_GR_PAGE_LIMIT", "100"))
    if not 1 <= page_limit <= 1000:
        raise ValueError("Invalid GR page limit")
    clock = time.time() if now is None else now
    deadline = float("inf") if deadline is None else deadline
    current = lambda: time.time() if now is None else now
    state_path = root / "favi-gr-schedule.json"
    state = _read_state(state_path)
    if should_stop():
        return {"status": "interrupted"}
    if clock < state.get("retry_at", 0):
        return {"status": "retry_wait", "retry_at": state["retry_at"]}
    if not state.get("generation"):
        if clock < state.get("next_run_at", 0):
            return {"status": "waiting", "next_run_at": state["next_run_at"]}
        state.update(generation=uuid.uuid4().hex, started_at=clock, retry_at=0)
        save(state_path, state)
    generation = state["generation"]
    if (not isinstance(generation, str) or len(generation) != 32
            or any(char not in "0123456789abcdef" for char in generation)):
        raise ValueError("Invalid GR generation ID")
    if current() >= deadline:
        return {"status": "yielded", "stage": "bg_deadline",
                "generation": generation}
    folder = root / "favi-gr-runs" / generation / "favi-gr-source"
    try:
        report_path = folder / "favi-gr-report.json"
        xml_path = folder / "favi-gr-private.xml"
        if report_path.exists() and xml_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not report.get("source_complete"):
                raise RuntimeError("Incomplete cached GR report")
        else:
            from .favi_gr_catalog import execute
            report = execute(batch_limit=page_limit, root=root, source_folder=folder,
                             publish=False, deadline=deadline,
                             should_stop=lambda: should_stop() or current() >= deadline)
        state.update(progress={"status": report["status"],
                               "source_products": report.get("source_products")},
                     updated_at=clock)
        save(state_path, state)
        if report["status"] in ("incomplete", "yielded") or should_stop() or current() >= deadline:
            status = ("interrupted" if should_stop() else "yielded"
                      if report["status"] == "yielded" or current() >= deadline
                      else "incomplete")
            return {"status": status, "stage": report.get("stage"),
                    "generation": generation, "source_products": report.get("source_products")}
        if not report.get("source_complete"):
            raise RuntimeError("Incomplete GR catalog generation")
        # A resumed scan from days ago cannot look current just because its
        # URL checks and report were regenerated today.
        if current() - state["started_at"] > MAX_SCAN_AGE_SECONDS:
            state.update(generation=None, rejected_generation=generation,
                         last_error="StaleGeneration", next_run_at=clock + 300)
            save(state_path, state)
            return {"status": "stale_generation_rejected", "generation": generation}
        if os.getenv("FEED_FAVI_GR_PREVIEW_PUBLISH") == "yes":
            from .favi_gr_delivery import publish_preview
            receipt = publish_preview(root, source_folder=folder)
        else:
            receipt = {"status": "private_complete", "items": report["xml_items"]}
        completed = time.time() if now is None else now
        state.update(generation=None, last_generation=generation,
                     last_success_at=completed, next_run_at=completed + interval,
                     last_items=receipt["items"], receipt=receipt,
                     last_error=None, retry_at=0)
        save(state_path, state)
        _clean_runs(root)
        return {**receipt, "generation": generation,
                "next_run_at": state["next_run_at"]}
    except RuntimeError as exc:
        if str(exc) == "FAVI GR preview count declined; keep previous pointer":
            # Keep both journals and the public pointer. A later fresh scan may
            # recover, without repeating expensive checks every 30 seconds.
            state.update(generation=None, rejected_generation=generation,
                         last_error="CountDeclined", next_run_at=clock + interval)
            save(state_path, state)
            return {"status": "count_declined_kept_previous", "generation": generation,
                    "next_run_at": state["next_run_at"]}
        state.update(last_error=type(exc).__name__, retry_at=clock + 300)
        save(state_path, state)
        raise
    except Exception as exc:
        state.update(last_error=type(exc).__name__, retry_at=clock + 300)
        save(state_path, state)
        raise
