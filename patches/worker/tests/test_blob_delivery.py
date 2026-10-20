import hashlib
import json
from feeds import blob_delivery
from feeds.xml_export import generate
from test_xml_audit import good_row
import pytest


def test_pointer_changes_only_after_read_back_verifies_both_snapshots(monkeypatch, tmp_path):
    folder = tmp_path / "google-bg"
    folder.mkdir()
    # Quantity zero + CONTINUE must survive the complete publication pipeline.
    row = {**good_row(), "available": False, "continue_selling": True}
    content = generate([row], "BG", "google")
    (folder / "google-bg-corrected-unpublished.xml").write_bytes(content)
    objects, writes = {}, []
    class Store:
        def __init__(self, token): pass
        def read(self, path): return objects.get(path), '"v1"'
        def put(self, path, data, kind, **options):
            writes.append(path)
            objects[path] = data
    monkeypatch.setattr(blob_delivery, "BlobStore", Store)
    monkeypatch.setattr(blob_delivery.os.path, "ismount", lambda path: True)
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setenv("FEED_GOOGLE_COMPARISON_PUBLISH", "yes")
    monkeypatch.delenv("FEED_REFERENCE_AUDIT_URL", raising=False)
    receipt = blob_delivery.publish_comparison(tmp_path)
    pointer = json.loads(objects[blob_delivery.MANIFEST])
    assert writes[-1] == blob_delivery.MANIFEST
    assert pointer["items"] == 1 and pointer["purpose"] == "comparison"
    assert not pointer["destination_accepted"]
    assert objects[pointer["xml_pathname"]] == content
    assert receipt["comparison_status"] == "reference_url_not_configured"
    # A broken object must not overwrite the prior good pointer.
    previous = objects[blob_delivery.MANIFEST]
    objects[pointer["xml_pathname"]] = b"truncated"
    with pytest.raises(RuntimeError, match="verification"):
        blob_delivery.publish_comparison(tmp_path)
    assert objects[blob_delivery.MANIFEST] == previous


def test_reference_fetch_rejects_other_hosts_before_request():
    for url in ("http://feedhub-storage.onecommerce.io/do/data_feed/google_feed/a.xml",
                "https://evil.test/feed.xml", "https://feedhub-storage.onecommerce.io/admin"):
        with pytest.raises(ValueError):
            blob_delivery.download_reference(url)
