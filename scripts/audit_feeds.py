#!/usr/bin/env python3
"""Inspect the bundled Homesector Hub source for feed functionality.

Run from repository root: python scripts/audit_feeds.py
Does not need credentials or modify the repository.
"""
from pathlib import Path
import base64
import io
import json
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PARTS = sorted((ROOT / "source-bundle").glob("part-*.txt"))
KEYWORDS = re.compile(r"feed|merchant|product_type|google.shopping|xml", re.I)
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".xml", ".yaml", ".yml"}
result = {"parts": len(PARTS), "files": 0, "matched_files": [], "errors": []}
if not PARTS:
    result["errors"].append("No source-bundle parts found")
else:
    try:
        payload = base64.b64decode("".join(p.read_text().strip() for p in PARTS), validate=True)
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                result["files"] += 1
                path = Path(member.name)
                if path.suffix.lower() not in TEXT_SUFFIXES or member.size > 2_000_000:
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    continue
                text = stream.read().decode("utf-8", errors="replace")
                lines = [i for i, line in enumerate(text.splitlines(), 1) if KEYWORDS.search(line)]
                if lines or KEYWORDS.search(member.name):
                    result["matched_files"].append({"path": member.name, "matching_lines": lines[:30], "total_matches": len(lines)})
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(1 if result["errors"] else 0)
