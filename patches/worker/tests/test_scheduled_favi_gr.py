import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feeds import scheduled_favi_gr


class ScheduledGreekFeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {
            "FEED_DURABLE_STORAGE_CONFIRMED": "yes",
            "FEED_FAVI_GR_PREVIEW_PUBLISH": "yes",
            "FEED_FAVI_GR_REGENERATE_SECONDS": "86400",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.mount = patch.object(scheduled_favi_gr.os.path, "ismount", return_value=True)
        self.mount.start()
        self.addCleanup(self.mount.stop)

    def _modules(self, scan, publish):
        fake_catalog = types.ModuleType("feeds.favi_gr_catalog")
        fake_catalog.execute = scan
        fake_delivery = types.ModuleType("feeds.favi_gr_delivery")
        fake_delivery.publish_preview = publish
        return patch.dict(sys.modules, {
            "feeds.favi_gr_catalog": fake_catalog,
            "feeds.favi_gr_delivery": fake_delivery,
        })

    def test_generation_resumes_and_daily_wait_is_cheap(self):
        scans, publications = [], []

        def scan(**kwargs):
            scans.append(kwargs["source_folder"])
            folder = kwargs["source_folder"]
            folder.mkdir(parents=True, exist_ok=True)
            if len(scans) == 1:
                return {"status": "incomplete", "source_products": 500}
            report = {"status": "unpublished_preview", "source_complete": True,
                      "source_products": 20000, "xml_items": 300}
            (folder / "favi-gr-report.json").write_text(json.dumps(report))
            (folder / "favi-gr-private.xml").write_text("xml")
            return report

        def publish(mount, source_folder):
            publications.append(source_folder)
            return {"status": "partial_preview_uploaded", "items": 300}

        with self._modules(scan, publish):
            first = scheduled_favi_gr.tick(self.root, now=1000)
            second = scheduled_favi_gr.tick(self.root, now=1020)
            third = scheduled_favi_gr.tick(self.root, now=1100)
        self.assertEqual(first["status"], "incomplete")
        self.assertEqual(second["status"], "partial_preview_uploaded")
        self.assertEqual(third["status"], "waiting")
        self.assertEqual(scans[0], scans[1])
        self.assertEqual(publications, [scans[1]])
        self.assertEqual(len(scans), 2)

    def test_publication_failure_retries_cached_generation(self):
        scans, publications = [], []

        def scan(**kwargs):
            scans.append(1)
            folder = kwargs["source_folder"]
            folder.mkdir(parents=True, exist_ok=True)
            report = {"status": "unpublished_preview", "source_complete": True,
                      "source_products": 20000, "xml_items": 300}
            (folder / "favi-gr-report.json").write_text(json.dumps(report))
            (folder / "favi-gr-private.xml").write_text("xml")
            return report

        def publish(mount, source_folder):
            publications.append(1)
            if len(publications) == 1:
                raise ConnectionError("Blob unavailable")
            return {"status": "partial_preview_uploaded", "items": 300}

        with self._modules(scan, publish):
            with self.assertRaises(ConnectionError):
                scheduled_favi_gr.tick(self.root, now=1000)
            self.assertEqual(scheduled_favi_gr.tick(self.root, now=1200)["status"],
                             "retry_wait")
            result = scheduled_favi_gr.tick(self.root, now=1300)
        self.assertEqual(result["status"], "partial_preview_uploaded")
        self.assertEqual(len(scans), 1)
        self.assertEqual(len(publications), 2)

    def test_decline_keeps_pointer_and_schedules_new_generation(self):
        publications = []

        def scan(**kwargs):
            folder = kwargs["source_folder"]
            folder.mkdir(parents=True, exist_ok=True)
            report = {"status": "unpublished_preview", "source_complete": True,
                      "source_products": 20000, "xml_items": 100}
            (folder / "favi-gr-report.json").write_text(json.dumps(report))
            (folder / "favi-gr-private.xml").write_text("xml")
            return report

        def publish(mount, source_folder):
            publications.append(1)
            raise RuntimeError("FAVI GR preview count declined; keep previous pointer")

        with self._modules(scan, publish):
            result = scheduled_favi_gr.tick(self.root, now=1000)
            waiting = scheduled_favi_gr.tick(self.root, now=1100)
        self.assertEqual(result["status"], "count_declined_kept_previous")
        self.assertEqual(waiting["status"], "waiting")
        self.assertEqual(len(publications), 1)
        state = json.loads((self.root / "favi-gr-schedule.json").read_text())
        self.assertIsNone(state["generation"])
        self.assertEqual(state["last_error"], "CountDeclined")

    def test_stale_resumed_scan_is_not_published(self):
        publications = []

        def scan(**kwargs):
            folder = kwargs["source_folder"]
            folder.mkdir(parents=True, exist_ok=True)
            return {"status": "incomplete", "source_products": 500}

        def publish(mount, source_folder):
            publications.append(1)
            return {"status": "partial_preview_uploaded", "items": 300}

        with self._modules(scan, publish):
            first = scheduled_favi_gr.tick(self.root, now=1000)
            folder = self.root / "favi-gr-runs" / first["generation"] / "favi-gr-source"
            report = {"status": "unpublished_preview", "source_complete": True,
                      "source_products": 20000, "xml_items": 300}
            (folder / "favi-gr-report.json").write_text(json.dumps(report))
            (folder / "favi-gr-private.xml").write_text("xml")
            old = scheduled_favi_gr.tick(
                self.root, now=1000 + scheduled_favi_gr.MAX_SCAN_AGE_SECONDS + 1)
        self.assertEqual(old["status"], "stale_generation_rejected")
        self.assertFalse(publications)

    def test_deadline_yield_preserves_generation_without_publication(self):
        calls, publications = [], []

        def scan(**kwargs):
            calls.append(kwargs["source_folder"])
            if len(calls) == 1:
                return {"status": "yielded", "stage": "direct_urls",
                        "source_products": 19303}
            folder = kwargs["source_folder"]
            folder.mkdir(parents=True, exist_ok=True)
            report = {"status": "unpublished_preview", "source_complete": True,
                      "source_products": 19303, "xml_items": 300}
            (folder / "favi-gr-report.json").write_text(json.dumps(report))
            (folder / "favi-gr-private.xml").write_text("xml")
            return report

        def publish(mount, source_folder):
            publications.append(source_folder)
            return {"status": "partial_preview_uploaded", "items": 300}

        with self._modules(scan, publish):
            first = scheduled_favi_gr.tick(self.root, now=1000, deadline=1050)
            self.assertEqual(first["status"], "yielded")
            self.assertFalse(publications)
            second = scheduled_favi_gr.tick(self.root, now=1100, deadline=1300)
        self.assertEqual(second["status"], "partial_preview_uploaded")
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(publications, [calls[1]])


if __name__ == "__main__":
    unittest.main()
