"""Publish an audited BG preview pointer; no FAVI account is changed."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .blob_delivery import BlobStore
from .favi_gr_audit import audit_favi_gr
from .xml_audit import validate_xml

PREFIX = "feeds/favi-bg/"
MANIFEST = PREFIX + "current-preview.json"


def publish_preview(mount, source_folder):
    root = Path(mount).resolve()
    if os.getenv("FEED_FAVI_BG_PREVIEW_PUBLISH") != "yes":
        return {"status": "disabled", "published": False}
    if os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes" or not os.path.ismount(root):
        raise RuntimeError("Confirmed mounted feed storage required")
    folder = Path(source_folder).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("BG preview must reside on confirmed disk")
    xml = (folder / "favi-bg-id-migration-candidate.xml").read_bytes()
    report = json.loads((folder / "favi-bg-preview-report.json").read_text(encoding="utf-8"))
    audit = validate_xml(xml, "BG", max_issues=0)
    favi_audit = audit_favi_gr(xml)
    if (not report.get("id_migration_candidate_items") or not audit["passed"]
            or audit["items"] != report.get("id_migration_candidate_items")
            or hashlib.sha256(xml).hexdigest() != report.get("id_migration_candidate_sha256")
            or audit["unique_ids"] != audit["items"] or not favi_audit["passed"]):
        raise RuntimeError("Incomplete or invalid FAVI BG preview")
    # The builder also writes a smaller private preview without migrated IDs.
    # The public report must describe the XML selected by this pointer.
    report["private_preview_xml_items"] = report["xml_items"]
    report["private_preview_sha256"] = report["sha256"]
    report["xml_items"] = audit["items"]
    report["sha256"] = hashlib.sha256(xml).hexdigest()
    report["published_source"] = "id_migration_candidate"
    report["id_migration_review_required"] = bool(report.get("blocked_legacy_id_migration"))
    report["favi_bg_preflight_audit"] = favi_audit
    report["id_migration_notice"] = (
        "Existing legacy IDs with forbidden characters are replaced by stable FAVI-safe IDs; "
        "FAVI may reindex these products."
    )
    report["published"] = True
    report["status"] = "partial_preview_published"
    store = BlobStore(os.getenv("FEED_BLOB_READ_WRITE_TOKEN", ""), prefix=PREFIX)
    old, etag = store.read(MANIFEST)
    if old is not None:
        previous = json.loads(old)
        if (not etag or previous.get("market") != "BG"
                or previous.get("purpose") != "partial_preview"
                or not isinstance(previous.get("items"), int)):
            raise RuntimeError("Invalid previous FAVI BG pointer")
        if audit["items"] < previous["items"]:
            raise RuntimeError("FAVI BG preview count declined; keep previous pointer")
    xml_hash = hashlib.sha256(xml).hexdigest()
    report_bytes = json.dumps(report, ensure_ascii=False, sort_keys=True).encode()
    report_hash = hashlib.sha256(report_bytes).hexdigest()
    paths = ((PREFIX + "snapshots/" + xml_hash + ".xml", xml,
              "application/xml; charset=utf-8"),
             (PREFIX + "snapshots/" + report_hash + ".json", report_bytes,
              "application/json; charset=utf-8"))
    for path, data, kind in paths:
        existing, _ = store.read(path)
        if existing is None:
            store.put(path, data, kind)
            existing, _ = store.read(path)
        if existing is None or hashlib.sha256(existing).digest() != hashlib.sha256(data).digest():
            raise RuntimeError("FAVI BG snapshot verification failed")
    pointer = json.dumps({
        "version": 1, "channel": "favi", "market": "BG", "purpose": "partial_preview",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": audit["items"], "bytes": len(xml), "sha256": xml_hash,
        "report_sha256": report_hash,
        "xml_pathname": paths[0][0], "report_pathname": paths[1][0],
        "approved_by_favi": False, "destination_subscriptions_changed": False,
    }, ensure_ascii=False).encode()
    store.put(MANIFEST, pointer, "application/json", overwrite=old is not None, etag=etag)
    checked, _ = store.read(MANIFEST)
    if checked != pointer:
        raise RuntimeError("FAVI BG preview pointer verification failed")
    return {"status": "partial_preview_uploaded", "report_version": 2,
            "items": audit["items"],
            "sha256": xml_hash, "approved_by_favi": False,
            "destination_subscriptions_changed": False}
