"""RO preview pointer must not move on an empty or partial source."""
import json

import pytest

from feeds import favi_ro_delivery as delivery


def test_ro_publisher_rejects_incomplete_source_before_blob_access(tmp_path, monkeypatch):
    monkeypatch.setenv("FEED_FAVI_RO_PREVIEW_PUBLISH", "yes")
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setattr(delivery.os.path, "ismount", lambda _: True)
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "favi-ro-private.xml").write_bytes(
        b'<rss version="2.0"><channel><title>RO</title></channel></rss>')
    (folder / "favi-ro-report.json").write_text(json.dumps({
        "source_complete": False, "xml_items": 0}))
    monkeypatch.setattr(delivery, "BlobStore", lambda *a, **kw: pytest.fail(
        "Private Blob must not be accessed for a partial preview"))
    with pytest.raises(RuntimeError, match="Incomplete or invalid"):
        delivery.publish_preview(tmp_path, folder)
