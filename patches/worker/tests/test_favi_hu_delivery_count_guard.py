"""An audited HU refresh can decline modestly without hiding a large loss."""
import json

import pytest

from feeds import favi_hu_delivery as delivery


class MemoryBlobStore:
    data = {}

    def __init__(self, *args, **kwargs):
        pass

    def read(self, path):
        value = self.data.get(path)
        return value, "etag" if value is not None else None

    def put(self, path, value, kind, overwrite=False, etag=None):
        self.data[path] = value


@pytest.mark.parametrize("items,allowed", [(4402, True), (3600, False)])
def test_hu_count_guard(tmp_path, monkeypatch, items, allowed):
    monkeypatch.setenv("FEED_FAVI_HU_PREVIEW_PUBLISH", "yes")
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setattr(delivery.os.path, "ismount", lambda _: True)
    monkeypatch.setattr(delivery, "validate_xml", lambda *a, **kw: {
        "passed": True, "items": items, "unique_ids": items})
    monkeypatch.setattr(delivery, "audit_favi_gr", lambda _: {"passed": True})
    monkeypatch.setattr(delivery, "BlobStore", MemoryBlobStore)
    source = tmp_path / "source"
    source.mkdir()
    (source / "favi-hu-private.xml").write_bytes(b"audited XML")
    (source / "favi-hu-report.json").write_text(json.dumps({
        "source_complete": True, "xml_items": items}))
    MemoryBlobStore.data = {delivery.MANIFEST: json.dumps({
        "market": "HU", "purpose": "partial_preview", "items": 4521,
    }).encode()}
    if allowed:
        assert delivery.publish_preview(tmp_path, source)["items"] == items
    else:
        with pytest.raises(RuntimeError, match="more than 20 percent"):
            delivery.publish_preview(tmp_path, source)
        assert json.loads(MemoryBlobStore.data[delivery.MANIFEST])["items"] == 4521
