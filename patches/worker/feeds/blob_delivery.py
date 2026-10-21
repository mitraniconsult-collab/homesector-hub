"""Publish a separate comparison XML through the Hub's existing private Blob.

Uses the documented @vercel/blob 2.8 request protocol (API version 12).
Immutable snapshot objects are verified by download before the current pointer
is replaced. No destination account or existing feed subscription is changed.
"""
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
import requests
from .feedhub_comparison import compare_snapshots, reconcile_ids
from .xml_audit import validate_xml

PREFIX = "feeds/google-bg/"
MANIFEST = PREFIX + "current.json"


class BlobStore:
    def __init__(self, token, prefix=PREFIX):
        parts = token.split("_")
        if not token.startswith("vercel_blob_rw_") or len(parts) < 5 or not parts[3].isalnum():
            raise ValueError("Feed Blob credential is not configured")
        if prefix not in (PREFIX, 'feeds/favi-gr/'):
            raise ValueError('Invalid feed Blob prefix')
        self.token, self.store_id, self.prefix = token, parts[3], prefix

    def headers(self):
        return {"Authorization": "Bearer " + self.token,
                "x-api-version": "12", "x-vercel-blob-store-id": self.store_id,
                "Accept-Encoding": "identity"}

    def read(self, pathname):
        if not pathname.startswith(self.prefix) or ".." in pathname:
            raise ValueError("Invalid feed Blob path")
        url = f"https://{self.store_id.lower()}.private.blob.vercel-storage.com/{pathname}"
        response = requests.get(url, params={"cache": "0"},
                                headers=self.headers(), timeout=(15, 120), allow_redirects=False)
        if response.status_code == 404:
            return None, None
        if response.status_code != 200:
            raise RuntimeError(f"Feed Blob read failed HTTP {response.status_code}")
        return response.content, response.headers.get("etag")

    def put(self, pathname, data, content_type, overwrite=False, etag=None):
        if not pathname.startswith(self.prefix) or ".." in pathname:
            raise ValueError("Invalid feed Blob path")
        headers = {**self.headers(), "x-vercel-blob-access": "private",
                   "x-add-random-suffix": "0", "x-allow-overwrite": "1" if overwrite else "0",
                   "x-content-type": content_type, "x-cache-control-max-age": "60"}
        if etag:
            headers["x-if-match"] = etag
        for attempt in range(4):
            response = requests.put("https://vercel.com/api/blob/", params={"pathname": pathname},
                                    data=data, headers=headers, timeout=(15, 180), allow_redirects=False)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            if response.status_code not in (200, 201):
                raise RuntimeError(f"Feed Blob upload failed HTTP {response.status_code}")
            break


def download_reference(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "feedhub-storage.onecommerce.io"
            or not parsed.path.startswith("/do/data_feed/google_feed/")
            or not parsed.path.endswith(".xml") or parsed.username or parsed.password):
        raise ValueError("Feedhub reference is not the approved XML host/path")
    with requests.get(url, stream=True, timeout=(15, 120), allow_redirects=False) as response:
        if response.status_code != 200:
            raise RuntimeError(f"Feedhub read failed HTTP {response.status_code}")
        data, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 250 * 1024 * 1024:
                raise ValueError("Feedhub reference too large")
            data.append(chunk)
    return b"".join(data)


def publish_comparison(mount, source_folder=None):
    if os.getenv("FEED_GOOGLE_COMPARISON_PUBLISH") != "yes":
        return {"status": "disabled"}
    root = Path(mount)
    if os.getenv("FEED_DURABLE_STORAGE_CONFIRMED") != "yes" or not os.path.ismount(root):
        raise RuntimeError("Confirmed mounted feed storage required")
    folder = (Path(source_folder) if source_folder else root / "google-bg").resolve()
    if not folder.is_relative_to(root.resolve()):
        raise ValueError("Catalog folder must be on the confirmed feed mount")
    store = BlobStore(os.getenv("FEED_BLOB_READ_WRITE_TOKEN", ""))
    source = folder / "google-bg-corrected-unpublished.xml"
    xml = source.read_bytes()
    reference = os.getenv("FEED_REFERENCE_AUDIT_URL", "").strip()
    if not reference:
        # A readable public candidate is still useful, but no comparison is
        # fabricated and no historical IDs are guessed.
        comparison = {"status": "reference_url_not_configured",
                      "destination_subscriptions_changed": False}
    else:
        baseline = download_reference(reference)
        xml, continuity = reconcile_ids(baseline, xml)
        comparison = {**compare_snapshots(baseline, xml), **continuity,
                      "feedhub_sha256": hashlib.sha256(baseline).hexdigest()}
        (folder / "feedhub-comparison-baseline.xml").write_bytes(baseline)
    audit = validate_xml(xml, "BG", max_issues=0)
    if not audit["items"] or audit["unique_ids"] != audit["items"]:
        raise ValueError("Cannot publish empty or duplicate-ID comparison XML")
    # Content issues remain visible in diagnostics. This is a public comparison
    # candidate, not an assertion of Merchant Center or FAVI acceptance.
    digest = hashlib.sha256(xml).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    comparison.update(checked_at=now, homesector_sha256=digest,
                      xml_preflight=audit, purpose="comparison")
    report_bytes = json.dumps(comparison, ensure_ascii=False, indent=2).encode()
    report_digest = hashlib.sha256(report_bytes).hexdigest()
    xml_path = PREFIX + "snapshots/" + digest + ".xml"
    report_path = PREFIX + "snapshots/" + report_digest + ".json"
    old_pointer, old_etag = store.read(MANIFEST)
    if old_pointer is not None and not old_etag:
        raise RuntimeError("Feed pointer is missing its storage ETag")
    for path, data, kind in ((xml_path, xml, "application/xml; charset=utf-8"),
                             (report_path, report_bytes, "application/json; charset=utf-8")):
        existing, _ = store.read(path)
        if existing is None:
            store.put(path, data, kind)
            existing, _ = store.read(path)
        if existing is None or hashlib.sha256(existing).digest() != hashlib.sha256(data).digest():
            raise RuntimeError("Feed Blob content verification failed")
    base = "https://hub.homesector.bg"
    manifest = {"version": 1, "channel": "google", "market": "BG",
                "purpose": "comparison", "generated_at": now, "items": audit["items"],
                "sha256": digest, "bytes": len(xml), "xml_pathname": xml_path,
                "comparison_pathname": report_path, "comparison_sha256": report_digest,
                "xml_url": base + "/feeds/google/BG.xml",
                "comparison_url": base + "/feeds/google/BG-comparison.json",
                "destination_accepted": False, "content_issues": audit["issues"]}
    pointer = json.dumps(manifest, ensure_ascii=False).encode()
    store.put(MANIFEST, pointer, "application/json", overwrite=old_pointer is not None, etag=old_etag)
    check, _ = store.read(MANIFEST)
    if check != pointer:
        raise RuntimeError("Published feed pointer verification failed")
    (folder / "google-bg-public-comparison.xml").write_bytes(xml)
    (folder / "feedhub-comparison.json").write_bytes(report_bytes)
    receipt = {"status": "comparison_snapshot_uploaded", "items": audit["items"],
               "sha256": digest, "xml_url": manifest["xml_url"],
               "comparison_url": manifest["comparison_url"],
               "comparison_status": comparison["status"],
               "summary": {key: comparison.get(key) for key in
                           ("feedhub_items", "matched_variants", "only_feedhub", "only_homesector",
                            "field_differences", "historical_ids_preserved")},
               "content_issues": audit["issues"], "destination_subscriptions_changed": False}
    (folder / "publication-receipt.json").write_text(json.dumps(receipt, indent=2))
    return receipt
