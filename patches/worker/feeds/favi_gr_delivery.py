"""Publish an explicitly partial FAVI GR preview from private verified snapshots.

No FAVI destination subscription is changed. The public URL is for human review.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .blob_delivery import BlobStore
from .xml_audit import validate_xml
from .favi_gr_audit import audit_favi_gr

PREFIX = "feeds/favi-gr/"
MANIFEST = PREFIX + "current-preview.json"


def publish_preview(mount, source_folder=None):
    root = Path(mount)
    if os.getenv("FEED_FAVI_GR_PREVIEW_PUBLISH") != "yes":
        return {"status": "disabled", "published": False}
    if os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes" or not os.path.ismount(root):
        raise RuntimeError("Confirmed mounted feed storage required")
    folder = Path(source_folder or root / "favi-gr-source").resolve()
    if not folder.is_relative_to(root.resolve()):
        raise ValueError("FAVI GR source folder must be on the confirmed mount")
    xml = (folder / "favi-gr-private.xml").read_bytes()
    report = json.loads((folder / "favi-gr-report.json").read_text(encoding="utf-8"))
    audit = validate_xml(xml, "GR", max_issues=0)
    favi_audit = audit_favi_gr(xml)
    if (not report.get("source_complete") or report.get("xml_items") != audit["items"]
            or not audit["passed"] or audit["unique_ids"] != audit["items"]
            or favi_audit["items"] != audit["items"] or not favi_audit["passed"]):
        raise RuntimeError("Incomplete or invalid FAVI GR preview: "
                           + json.dumps(favi_audit["issues"], sort_keys=True))
    report["favi_gr_preflight_audit"] = favi_audit
    store = BlobStore(os.getenv("FEED_BLOB_READ_WRITE_TOKEN", ""), prefix=PREFIX)
    old, etag = store.read(MANIFEST)
    if old is not None:
        if not etag:
            raise RuntimeError("FAVI GR preview pointer lacks storage ETag")
        previous = json.loads(old)
        if (previous.get("purpose") != "partial_preview"
                or previous.get("market") != "GR"
                or not isinstance(previous.get("items"), int)):
            raise RuntimeError("Invalid previous FAVI GR preview pointer")
        if audit["items"] < previous["items"]:
            raise RuntimeError("FAVI GR preview count declined; keep previous pointer")
    xml_digest = hashlib.sha256(xml).hexdigest()
    report_bytes = json.dumps(report, ensure_ascii=False, sort_keys=True).encode()
    report_digest = hashlib.sha256(report_bytes).hexdigest()
    xml_path = PREFIX + "snapshots/" + xml_digest + ".xml"
    report_path = PREFIX + "snapshots/" + report_digest + ".json"
    for path, data, mime in (
        (xml_path, xml, "application/xml; charset=utf-8"),
        (report_path, report_bytes, "application/json; charset=utf-8"),
    ):
        existing, _ = store.read(path)
        if existing is None:
            store.put(path, data, mime)
            existing, _ = store.read(path)
        if existing is None or hashlib.sha256(existing).digest() != hashlib.sha256(data).digest():
            raise RuntimeError("FAVI GR preview snapshot verification failed")
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "version": 1, "channel": "favi", "market": "GR", "purpose": "partial_preview",
        "generated_at": now, "items": audit["items"], "bytes": len(xml),
        "sha256": xml_digest, "report_sha256": report_digest,
        "xml_pathname": xml_path, "report_pathname": report_path,
        "approved_by_favi": False, "destination_subscriptions_changed": False,
    }
    pointer = json.dumps(manifest, ensure_ascii=False).encode()
    store.put(MANIFEST, pointer, "application/json", overwrite=old is not None, etag=etag)
    checked, _ = store.read(MANIFEST)
    if checked != pointer:
        raise RuntimeError("FAVI GR preview pointer verification failed")
    return {
        "status": "partial_preview_uploaded", "items": audit["items"],
        "sha256": xml_digest,
        "xml_url": "https://hub.homesector.bg/feeds/favi/GR-preview.xml",
        "report_url": "https://hub.homesector.bg/feeds/favi/GR-preview-report.json",
        "approved_by_favi": False, "destination_subscriptions_changed": False,
    }

