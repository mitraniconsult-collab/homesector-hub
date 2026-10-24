import json
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AlternateSourceFolderTests(unittest.TestCase):
    def test_audited_small_decline_publishes_but_material_decline_does_not(self):
        blob = types.ModuleType("feeds.blob_delivery")
        blob.BlobStore = object
        with patch.dict(sys.modules, {"feeds.blob_delivery": blob}):
            spec = importlib.util.spec_from_file_location(
                "feeds._favi_gr_delivery_count_guard_under_test",
                Path(__file__).resolve().parents[1] / "feeds" / "favi_gr_delivery.py")
            delivery = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(delivery)

        for count, should_publish in ((4765, True), (4500, False)):
            storage = {delivery.MANIFEST: json.dumps({
                "purpose": "partial_preview", "market": "GR", "items": 4766,
            }).encode()}

            class BlobStore:
                def __init__(self, token, prefix):
                    pass

                def read(self, path):
                    value = storage.get(path)
                    return value, "etag" if value is not None else None

                def put(self, path, data, mime, overwrite=False, etag=None):
                    storage[path] = data

            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "favi-gr-private.xml").write_bytes(b"<rss/>")
                (root / "favi-gr-report.json").write_text(json.dumps({
                    "source_complete": True, "xml_items": count,
                }))
                valid = {"items": count, "unique_ids": count, "passed": True,
                         "issues": {}}
                with patch.dict(os.environ, {
                    "FEED_DURABLE_STORAGE_CONFIRMED": "yes",
                    "FEED_FAVI_GR_PREVIEW_PUBLISH": "yes",
                }), patch.object(os.path, "ismount", return_value=True), \
                        patch.object(delivery, "BlobStore", BlobStore), \
                        patch.object(delivery, "validate_xml", return_value=valid), \
                        patch.object(delivery, "audit_favi_gr", return_value=valid):
                    if should_publish:
                        self.assertEqual(delivery.publish_preview(root, source_folder=root)["items"], count)
                        self.assertEqual(json.loads(storage[delivery.MANIFEST])["items"], count)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "count declined"):
                            delivery.publish_preview(root, source_folder=root)
                        self.assertEqual(json.loads(storage[delivery.MANIFEST])["items"], 4766)

    def test_complete_generation_uploads_without_touching_legacy_folder(self):
        storage = {}

        class BlobStore:
            def __init__(self, token, prefix):
                pass

            def read(self, path):
                value = storage.get(path)
                return value, "etag" if value else None

            def put(self, path, data, mime, overwrite=False, etag=None):
                storage[path] = data

        blob = types.ModuleType("feeds.blob_delivery")
        blob.BlobStore = BlobStore
        audit = types.ModuleType("feeds.xml_audit")
        audit.validate_xml = lambda xml, market, max_issues: {
            "items": 2, "unique_ids": 2, "passed": True,
        }
        with patch.dict(sys.modules, {
            "feeds.blob_delivery": blob, "feeds.xml_audit": audit,
        }):
            spec = importlib.util.spec_from_file_location(
                "feeds._favi_gr_delivery_under_test",
                Path(__file__).resolve().parents[1] / "feeds" / "favi_gr_delivery.py")
            favi_gr_delivery = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(favi_gr_delivery)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "favi-gr-runs" / ("a" * 32) / "favi-gr-source"
                source.mkdir(parents=True)
                (source / "favi-gr-private.xml").write_bytes(
                    b'<rss xmlns:g="http://base.google.com/ns/1.0"><channel>'
                    b'<item><g:id>one</g:id><link>https://homesector.gr/products/one?variant=1</link>'
                    b'<g:product_type>Category</g:product_type><g:item_group_id>parent</g:item_group_id>'
                    b'<title>One</title><description>One detail</description></item>'
                    b'<item><g:id>two</g:id><link>https://homesector.gr/products/one?variant=2</link>'
                    b'<g:product_type>Category</g:product_type><g:item_group_id>parent</g:item_group_id>'
                    b'<title>Two</title><description>Two detail</description></item>'
                    b'</channel></rss>')
                (source / "favi-gr-report.json").write_text(json.dumps({
                    "source_complete": True, "xml_items": 2,
                    "source_snapshot_at": "2026-10-21T12:00:00+00:00",
                    "generated_at": "2026-10-21T13:00:00+00:00",
                }))
                with patch.dict(os.environ, {
                    "FEED_DURABLE_STORAGE_CONFIRMED": "yes",
                    "FEED_FAVI_GR_PREVIEW_PUBLISH": "yes",
                }), patch.object(os.path, "ismount", return_value=True):
                    receipt = favi_gr_delivery.publish_preview(root, source_folder=source)
                self.assertEqual(receipt["items"], 2)
                manifest = json.loads(storage[favi_gr_delivery.MANIFEST])
                uploaded = json.loads(storage[manifest["report_pathname"]])
                self.assertEqual(uploaded["source_snapshot_at"],
                                 "2026-10-21T12:00:00+00:00")
                self.assertFalse((root / "favi-gr-source").exists())

    def test_source_folder_outside_mount_is_rejected(self):
        blob = types.ModuleType("feeds.blob_delivery")
        blob.BlobStore = object
        audit = types.ModuleType("feeds.xml_audit")
        audit.validate_xml = lambda *a, **k: {}
        with patch.dict(sys.modules, {
            "feeds.blob_delivery": blob, "feeds.xml_audit": audit,
        }):
            spec = importlib.util.spec_from_file_location(
                "feeds._favi_gr_delivery_under_test",
                Path(__file__).resolve().parents[1] / "feeds" / "favi_gr_delivery.py")
            favi_gr_delivery = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(favi_gr_delivery)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "mount"
                root.mkdir()
                with patch.dict(os.environ, {
                    "FEED_DURABLE_STORAGE_CONFIRMED": "yes",
                    "FEED_FAVI_GR_PREVIEW_PUBLISH": "yes",
                }), patch.object(os.path, "ismount", return_value=True):
                    with self.assertRaises(ValueError):
                        favi_gr_delivery.publish_preview(root, source_folder=Path(directory) / "other")


if __name__ == "__main__":
    unittest.main()
