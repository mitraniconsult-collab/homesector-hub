"""Filesystem-backed feed batch checkpoints, suitable ONLY for a durable mounted disk.

The runner deliberately refuses /tmp and other ephemeral paths. The manifest
advances atomically only after JSONL product records have been fsynced.
"""
import json
import os
from pathlib import Path

class DurableJournal:
    def __init__(self, root):
        root = Path(root).resolve()
        if str(root).startswith(("/tmp/", "/var/tmp/", "/dev/shm/")) or str(root) in ("/tmp", "/var/tmp"):
            raise ValueError("Feed checkpoint directory must be a durable mounted volume")
        if os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes":
            raise RuntimeError("Explicit durable storage configuration required")
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.records = root / "records.jsonl"
        self.manifest = root / "manifest.json"

    def load(self):
        if not self.manifest.exists():
            if self.records.exists():
                raise RuntimeError("Orphaned records without manifest; manual review required")
            return {"cursor": None, "items": 0, "products": 0, "bytes": 0, "finished": False}, []
        meta = json.loads(self.manifest.read_text(encoding="utf-8"))
        if meta["bytes"] < 0 or meta["items"] < 0:
            raise RuntimeError("Corrupt batch metadata")
        if not self.records.exists() or self.records.stat().st_size < meta["bytes"]:
            raise RuntimeError("Missing or truncated feed checkpoint")
        with self.records.open("r+b") as fh:
            fh.truncate(meta["bytes"])
        with self.records.open("r", encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        if len(rows) != meta["items"]:
            raise RuntimeError("Feed checkpoint count mismatch")
        return meta, rows

    def commit(self, cursor, rows, products, finished=False):
        previous, _ = self.load()
        if products < previous["products"] or len(rows) < previous["items"]:
            raise RuntimeError("Checkpoint regression")
        # The cursor must belong to the last *fully processed* Shopify page.
        with self.records.open("ab") as fh:
            for row in rows[previous["items"]:]:
                fh.write((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
            fh.flush()
            os.fsync(fh.fileno())
            byte_count = fh.tell()
        new_meta = {"cursor": cursor, "products": products,
                    "items": len(rows), "bytes": byte_count, "finished": bool(finished)}
        temp = self.manifest.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as fh:
            json.dump(new_meta, fh, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, self.manifest)
        return new_meta
