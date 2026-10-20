"""Read-only quality audit of private snapshots on the worker's mounted disk.

Reports describe local artifacts, never destination acceptance or publication.
The API must have access to the same actual volume to return this report.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .xml_audit import validate_xml, validated_preview

REPORT_NAME = "feed-snapshot-diagnostics.json"
SNAPSHOTS = {
    "google": "google-bg/google-bg-unpublished.xml",
    "favi": "favi-bg-unpublished.xml",
}


def report_path():
    mount = os.getenv("FEED_DURABLE_PATH", "").strip()
    if (os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes"
            or not mount or not os.path.ismount(mount)):
        return None
    return Path(mount) / REPORT_NAME


def read_report():
    path = report_path()
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def audit_snapshots(mount):
    root = Path(mount)
    if (os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes"
            or not os.path.ismount(root)):
        raise RuntimeError("Snapshot audit requires a confirmed mounted volume")
    feeds = []
    for channel, filename in SNAPSHOTS.items():
        path = root / filename
        result = {"channel": channel, "market": "BG", "published": False,
                  "destination_accepted": False, "xml_url": None,
                  "release_ready": False}
        if not path.is_file():
            result.update(status="snapshot_missing", quality_passed=False)
        else:
            xml = path.read_bytes()
            result.update(sha256=hashlib.sha256(xml).hexdigest(), bytes=len(xml),
                          artifact_modified_at=datetime.fromtimestamp(
                              path.stat().st_mtime, timezone.utc).isoformat())
            try:
                audit = validate_xml(xml, "BG", max_issues=0)
                result.update(status="unpublished_snapshot", items=audit["items"],
                              unique_ids=audit["unique_ids"], issues=audit["issues"],
                              quality_passed=audit["passed"])
                if channel == "google":
                    candidate, candidate_report = validated_preview(xml, "BG")
                    candidate_path = path.with_name("google-bg-validated-preview.xml")
                    candidate_temp = candidate_path.with_suffix(".tmp")
                    with candidate_temp.open("wb") as file:
                        file.write(candidate)
                        file.flush()
                        os.fsync(file.fileno())
                    os.replace(candidate_temp, candidate_path)
                    candidate_report["sha256"] = hashlib.sha256(candidate).hexdigest()
                    result["validated_preview"] = candidate_report
            except (ValueError, SyntaxError):
                result.update(status="invalid_xml", quality_passed=False)
        feeds.append(result)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "storage": "mounted_persistent_volume", "feeds": feeds,
              "published": False, "scope": "local_xml_preflight_only"}
    path = root / REPORT_NAME
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, path)
    return report
