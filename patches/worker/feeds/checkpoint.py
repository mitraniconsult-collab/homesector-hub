"""Crash-consistent LOCAL progress journal for staging feed audit.

This is not durable across Render deployments or instance replacement.
Persisted cursor is only advanced after the matching variant rows are fsynced.
"""
import json
import os
from pathlib import Path

class LocalCheckpoint:
    def __init__(self, folder):
        self.root = Path(folder)
        self.root.mkdir(parents=True, exist_ok=True)
        self.data = self.root / "rows.jsonl"
        self.meta = self.root / "checkpoint.json"
        self.saved_count = 0

    def load(self):
        if not self.meta.exists():
            self.data.write_bytes(b"")
            return None, [], {}, 0, 0
        meta = json.loads(self.meta.read_text(encoding="utf-8"))
        offset = int(meta["byte_offset"])
        if not self.data.exists() or self.data.stat().st_size < offset:
            raise RuntimeError("Checkpoint journal is missing or truncated")
        with self.data.open("r+b") as handle:
            handle.truncate(offset)
        rows = []
        with self.data.open("r", encoding="utf-8") as handle:
            for line in handle:
                rows.append(json.loads(line))
        if len(rows) != meta["rows_count"]:
            raise RuntimeError("Checkpoint row count mismatch")
        self.saved_count = len(rows)
        if not meta.get("has_more", True):
            raise RuntimeError("Completed journal needs XML finalization")
        return (meta.get("next_cursor"), rows,
                meta.get("reasons", {}), int(meta["products_scanned"]),
                int(meta["variants_checked"]))

    def save(self, next_cursor, has_more, rows, reasons, products_scanned, variants_checked):
        if self.saved_count > len(rows):
            raise RuntimeError("Checkpoint row regression")
        with self.data.open("ab") as handle:
            for row in rows[self.saved_count:]:
                handle.write((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
            offset = handle.tell()
        state = {
            "next_cursor": next_cursor,
            "has_more": bool(has_more),
            "byte_offset": offset,
            "rows_count": len(rows),
            "reasons": dict(reasons),
            "products_scanned": products_scanned,
            "variants_checked": variants_checked,
        }
        tmp = self.meta.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.meta)
        self.saved_count = len(rows)

    def clear(self):
        self.meta.unlink(missing_ok=True)
        self.data.unlink(missing_ok=True)
