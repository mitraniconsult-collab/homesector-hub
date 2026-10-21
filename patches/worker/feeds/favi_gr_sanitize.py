"""One-time exact-ID correction of an already published FAVI GR preview.

Operator command: python -m feeds.favi_gr_sanitize --expected-sha <current XML SHA>
Add --apply only after reviewing the dry-run receipt. This does not update any
FAVI destination subscription or Shopify product.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from .blob_delivery import BlobStore
from .favi_gr_delivery import MANIFEST, PREFIX
from .xml_audit import G, validate_xml

BAD_GROUP_ID = "shopifyp8730408747275"
BAD_ITEM_ID = "shopifyv45644567052555"
BAD_CATEGORY = "Αποθήκευση τροφίμων > Δοχεία τροφίμων"
# Pinned to the audited 668-item preview; this module cannot sanitize a later
# generation or a different product by reusing the one-shot startup flag.
EXPECTED_CURRENT_SHA256 = "4f5921d8346a1fe6ccd6bc4fda07eebb9e2317f613fe2b340241c00b21cc7b70"


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _read_snapshot(store, path, digest):
    if not path.startswith(PREFIX + "snapshots/") or ".." in path:
        raise RuntimeError("Invalid current FAVI GR snapshot path")
    data, _ = store.read(path)
    if data is None or _digest(data) != digest:
        raise RuntimeError("Current FAVI GR snapshot checksum mismatch")
    return data


def _sanitize(xml, report, manifest):
    old_audit = validate_xml(xml, "GR", max_issues=0)
    if (not old_audit["passed"] or old_audit["items"] != manifest["items"]
            or report.get("xml_items") != old_audit["items"]
            or report.get("candidate_rows") != old_audit["items"]
            or report.get("sha256") != manifest["sha256"]
            or report.get("market") != "GR" or report.get("approved_by_favi") is not False
            or report.get("published") is not False or not report.get("source_complete")):
        raise RuntimeError("Current FAVI GR XML/report is not a complete audited pair")
    root = ET.fromstring(xml)
    channel = root.find("channel")
    matches = [item for item in channel.findall("item")
               if (item.findtext(G + "item_group_id") or "").strip() == BAD_GROUP_ID]
    if len(matches) != 1 or (matches[0].findtext(G + "product_type") or "").strip() != BAD_CATEGORY:
        raise RuntimeError("Expected exact bad product and category are not present once")
    removed_id = (matches[0].findtext(G + "id") or "").strip()
    if removed_id != BAD_ITEM_ID:
        raise RuntimeError("Unexpected FAVI variant ID for bad product")
    channel.remove(matches[0])
    ET.register_namespace("g", G[1:-1])
    corrected_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    new_audit = validate_xml(corrected_xml, "GR", max_issues=0)
    old_ids = {(item.findtext(G + "id") or "").strip()
               for item in ET.fromstring(xml).find("channel").findall("item")}
    new_ids = {(item.findtext(G + "id") or "").strip()
               for item in channel.findall("item")}
    if (not new_audit["passed"] or new_audit["items"] != old_audit["items"] - 1
            or old_ids - new_ids != {removed_id} or new_ids - old_ids):
        raise RuntimeError("Exact-ID FAVI GR correction audit failed")
    corrected_report = dict(report)
    corrected_report.update(
        xml_items=new_audit["items"], candidate_rows=new_audit["items"],
        sha256=_digest(corrected_xml),
        manual_correction={
            "reason": "incorrect_shopify_food_storage_category",
            "removed_item_id": removed_id,
            "removed_group_id": BAD_GROUP_ID,
            "previous_xml_sha256": manifest["sha256"],
            "source_metrics_as_of_previous_scan": True,
        },
    )
    return corrected_xml, corrected_report, removed_id


def correct_current_preview(expected_sha256, apply=False, store=None):
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("Explicit lowercase current XML SHA-256 required")
    store = store or BlobStore(os.getenv("FEED_BLOB_READ_WRITE_TOKEN", ""), prefix=PREFIX)
    old_bytes, etag = store.read(MANIFEST)
    if old_bytes is None or not etag:
        raise RuntimeError("Current FAVI GR pointer and ETag required")
    old = json.loads(old_bytes)
    if (old.get("correction") == {
            "removed_item_id": BAD_ITEM_ID, "removed_group_id": BAD_GROUP_ID,
            "previous_xml_sha256": expected_sha256,
            } and old.get("items") == 667 and old.get("sha256") != expected_sha256):
        return {"status": "already_corrected", "items": 667,
                "sha256": old["sha256"], "destination_subscriptions_changed": False}
    if (old.get("purpose") != "partial_preview" or old.get("market") != "GR"
            or old.get("approved_by_favi") is not False
            or old.get("destination_subscriptions_changed") is not False
            or old.get("sha256") != expected_sha256
            or old.get("items") != 668):
        raise RuntimeError("FAVI GR pointer changed or is not a partial preview")
    xml = _read_snapshot(store, old.get("xml_pathname", ""), expected_sha256)
    report_bytes = _read_snapshot(store, old.get("report_pathname", ""), old.get("report_sha256", ""))
    report = json.loads(report_bytes)
    corrected_xml, corrected_report, removed_id = _sanitize(xml, report, old)
    receipt = {
        "status": "dry_run", "previous_items": old["items"],
        "corrected_items": corrected_report["xml_items"],
        "removed_item_id": removed_id, "removed_group_id": BAD_GROUP_ID,
        "previous_sha256": expected_sha256,
        "corrected_sha256": _digest(corrected_xml),
        "destination_subscriptions_changed": False,
    }
    if not apply:
        return receipt
    if os.getenv("FEED_FAVI_GR_CORRECT_KNOWN_CATEGORY") != "yes":
        raise RuntimeError("One-time FAVI GR correction is not enabled")
    corrected_at = datetime.now(timezone.utc).isoformat()
    corrected_report["manual_correction"]["corrected_at"] = corrected_at
    new_report_bytes = json.dumps(corrected_report, ensure_ascii=False, sort_keys=True).encode()
    report_digest = _digest(new_report_bytes)
    xml_path = PREFIX + "snapshots/" + _digest(corrected_xml) + ".xml"
    report_path = PREFIX + "snapshots/" + report_digest + ".json"
    for path, data, mime in (
        (xml_path, corrected_xml, "application/xml; charset=utf-8"),
        (report_path, new_report_bytes, "application/json; charset=utf-8"),
    ):
        existing, _ = store.read(path)
        if existing is None:
            store.put(path, data, mime)
            existing, _ = store.read(path)
        if existing != data:
            raise RuntimeError("FAVI GR corrected immutable snapshot verification failed")
    new_pointer = dict(old)
    new_pointer.update(
        generated_at=corrected_at,
        items=corrected_report["xml_items"], bytes=len(corrected_xml),
        sha256=_digest(corrected_xml), report_sha256=report_digest,
        xml_pathname=xml_path, report_pathname=report_path,
        correction={"removed_item_id": removed_id, "removed_group_id": BAD_GROUP_ID,
                    "previous_xml_sha256": expected_sha256},
    )
    pointer_bytes = json.dumps(new_pointer, ensure_ascii=False).encode()
    store.put(MANIFEST, pointer_bytes, "application/json", overwrite=True, etag=etag)
    checked, _ = store.read(MANIFEST)
    if checked != pointer_bytes:
        raise RuntimeError("Corrected FAVI GR pointer verification failed")
    receipt["status"] = "corrected_partial_preview_uploaded"
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(correct_current_preview(args.expected_sha, apply=args.apply), sort_keys=True))


if __name__ == "__main__":
    main()
