"""The public BG report must describe the XML behind its pointer."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())
from feeds import favi_bg_delivery as delivery


class MemoryBlobStore:
    data = {}

    def __init__(self, *args, **kwargs):
        pass

    def read(self, path):
        value = self.data.get(path)
        return value, "etag" if value is not None else None

    def put(self, path, value, kind, overwrite=False, etag=None):
        self.data[path] = value


class BgDeliveryReportTest(unittest.TestCase):
    def test_report_matches_published_candidate(self):
        MemoryBlobStore.data = {}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = b"candidate XML"
            original = b"private XML"
            (root / "favi-bg-id-migration-candidate.xml").write_bytes(candidate)
            (root / "favi-bg-preview-report.json").write_text(json.dumps({
                "xml_items": 1,
                "sha256": hashlib.sha256(original).hexdigest(),
                "id_migration_candidate_items": 2,
                "id_migration_candidate_sha256": hashlib.sha256(candidate).hexdigest(),
                "blocked_legacy_id_migration": 1,
            }))
            audit = {"passed": True, "items": 2, "unique_ids": 2}
            with (patch.dict(delivery.os.environ, {
                    "FEED_FAVI_BG_PREVIEW_PUBLISH": "yes",
                    "FEED_DURABLE_STORAGE_CONFIRMED": "yes"}),
                    patch.object(delivery.os.path, "ismount", return_value=True),
                    patch.object(delivery, "validate_xml", return_value=audit),
                    patch.object(delivery, "audit_favi_gr", return_value={"passed": True}),
                    patch.object(delivery, "BlobStore", MemoryBlobStore)):
                receipt = delivery.publish_preview(root, root)
        pointer = json.loads(MemoryBlobStore.data[delivery.MANIFEST])
        report = json.loads(MemoryBlobStore.data[pointer["report_pathname"]])
        self.assertEqual(receipt["items"], 2)
        self.assertEqual(report["xml_items"], pointer["items"])
        self.assertEqual(report["sha256"], pointer["sha256"])
        self.assertEqual(report["private_preview_xml_items"], 1)
        self.assertEqual(report["private_preview_sha256"], hashlib.sha256(original).hexdigest())
        self.assertTrue(report["id_migration_review_required"])


if __name__ == "__main__":
    unittest.main()
