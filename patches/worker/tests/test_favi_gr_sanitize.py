"""Focused tests for the exact coffee-grinder correction and pointer CAS."""
import hashlib
import json
import os
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from feeds.favi_gr_sanitize import (
    BAD_CATEGORY, BAD_GROUP_ID, BAD_ITEM_ID, PREFIX, MANIFEST,
    correct_current_preview,
)

G = "{http://base.google.com/ns/1.0}"


def fixture(wrong_category=BAD_CATEGORY):
    ET.register_namespace("g", G[1:-1])
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Homesector FAVI GR"
    ET.SubElement(channel, "link").text = "https://homesector.gr"
    ET.SubElement(channel, "description").text = "Homesector feed"
    for i in range(668):
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = "Μύλος καφέ" if i == 0 else "Προϊόν"
        ET.SubElement(item, "description").text = "Περιγραφή"
        ET.SubElement(item, "link").text = f"https://homesector.gr/products/product-{i}"
        fields = {
            "id": BAD_ITEM_ID if i == 0 else f"shopifyv{i + 1000000}",
            "image_link": "https://cdn.shopify.com/product.jpg",
            "product_type": wrong_category if i == 0 else "Κεριά",
            "item_group_id": BAD_GROUP_ID if i == 0 else f"shopifyp{i + 1000000}",
            "price": "13.2 EUR", "availability": "in_stock", "condition": "new",
        }
        for key, value in fields.items():
            ET.SubElement(item, G + key).text = value
    xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    digest = hashlib.sha256(xml).hexdigest()
    report = {
        "market": "GR", "approved_by_favi": False, "published": False,
        "source_complete": True, "xml_items": 668, "candidate_rows": 668,
        "sha256": digest,
    }
    report_bytes = json.dumps(report).encode()
    report_digest = hashlib.sha256(report_bytes).hexdigest()
    manifest = {
        "purpose": "partial_preview", "market": "GR", "approved_by_favi": False,
        "destination_subscriptions_changed": False, "items": 668, "sha256": digest,
        "xml_pathname": PREFIX + "snapshots/" + digest + ".xml",
        "report_pathname": PREFIX + "snapshots/" + report_digest + ".json",
        "report_sha256": report_digest,
    }
    return manifest, xml, report_bytes


class FakeStore:
    def __init__(self, manifest, xml, report):
        self.data = {
            MANIFEST: json.dumps(manifest).encode(),
            manifest["xml_pathname"]: xml,
            manifest["report_pathname"]: report,
        }
        self.writes = []

    def read(self, path):
        data = self.data.get(path)
        return data, '"current-etag"' if path == MANIFEST and data else None

    def put(self, path, data, _mime, overwrite=False, etag=None):
        if path == MANIFEST:
            assert overwrite and etag == '"current-etag"'
        else:
            assert not overwrite and path not in self.data
        self.data[path] = data
        self.writes.append(path)


class CorrectionTest(unittest.TestCase):
    def test_dry_run_and_apply_remove_only_exact_variant(self):
        manifest, xml, report = fixture()
        store = FakeStore(manifest, xml, report)
        dry = correct_current_preview(manifest["sha256"], store=store)
        self.assertEqual(dry["corrected_items"], 667)
        self.assertEqual(dry["removed_item_id"], BAD_ITEM_ID)
        self.assertEqual(store.writes, [])
        with patch.dict(os.environ, {"FEED_FAVI_GR_CORRECT_KNOWN_CATEGORY": "yes"}):
            applied = correct_current_preview(manifest["sha256"], apply=True, store=store)
        self.assertEqual(applied["status"], "corrected_partial_preview_uploaded")
        self.assertEqual(store.writes[-1], MANIFEST)
        pointer = json.loads(store.data[MANIFEST])
        corrected = store.data[pointer["xml_pathname"]]
        self.assertNotIn(BAD_GROUP_ID.encode(), corrected)
        self.assertIn(b"shopifyv1000001", corrected)
        self.assertEqual(json.loads(store.data[pointer["report_pathname"]])["xml_items"], 667)
        self.assertEqual(correct_current_preview(manifest["sha256"], store=store)["status"], "already_corrected")

    def test_wrong_category_cannot_be_sanitized(self):
        manifest, xml, report = fixture("Κεριά")
        store = FakeStore(manifest, xml, report)
        with self.assertRaisesRegex(RuntimeError, "Expected exact bad product"):
            correct_current_preview(manifest["sha256"], store=store)
        self.assertFalse(store.writes)

    def test_stale_pointer_sha_cannot_be_sanitized(self):
        manifest, xml, report = fixture()
        store = FakeStore(manifest, xml, report)
        with self.assertRaisesRegex(RuntimeError, "pointer changed"):
            correct_current_preview("0" * 64, store=store)
        self.assertFalse(store.writes)


if __name__ == "__main__":
    unittest.main()
