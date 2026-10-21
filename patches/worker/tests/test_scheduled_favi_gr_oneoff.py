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


class OneOffGreekRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, {
            "FEED_DURABLE_STORAGE_CONFIRMED": "yes",
            "FEED_FAVI_GR_PREVIEW_PUBLISH": "no",
            "FEED_FAVI_GR_REGENERATE_SECONDS": "86400",
        })
        env.start()
        self.addCleanup(env.stop)
        mount = patch.object(scheduled_favi_gr.os.path, "ismount", return_value=True)
        mount.start()
        self.addCleanup(mount.stop)

    def _fake_scan(self, function):
        module = types.ModuleType("feeds.favi_gr_catalog")
        module.execute = function
        return patch.dict(sys.modules, {"feeds.favi_gr_catalog": module})

    def test_new_token_runs_once_before_daily_due(self):
        path = self.root / "favi-gr-schedule.json"
        path.write_text(json.dumps({"generation": None, "next_run_at": 90000}))
        scans = []
        def scan(**kwargs):
            scans.append(kwargs["source_folder"])
            return {"status": "unpublished_preview", "source_complete": True,
                    "source_products": 20000, "xml_items": 3}
        with patch.dict(os.environ, {"FEED_FAVI_GR_REFRESH_TOKEN": "one-off-token-20261021-A"}), self._fake_scan(scan):
            first = scheduled_favi_gr.tick(self.root, now=1000, deadline=5000)
            second = scheduled_favi_gr.tick(self.root, now=1020, deadline=5000)
        self.assertEqual(first["status"], "private_complete")
        self.assertEqual(second["status"], "waiting")
        self.assertEqual(len(scans), 1)
        state = json.loads(path.read_text())
        self.assertEqual(state["next_run_at"], 87400)
        self.assertEqual(len(state["last_refresh_digest"]), 64)
        self.assertNotIn("one-off-token", path.read_text())

    def test_new_token_yields_to_bg_without_consumption(self):
        path = self.root / "favi-gr-schedule.json"
        path.write_text(json.dumps({"generation": None, "next_run_at": 90000}))
        calls = []
        with patch.dict(os.environ, {"FEED_FAVI_GR_REFRESH_TOKEN": "one-off-token-20261021-B"}), self._fake_scan(lambda **kwargs: calls.append(1) or {"status": "incomplete", "source_products": 100}):
            first = scheduled_favi_gr.tick(self.root, now=1000, deadline=1000)
            state_before = path.read_text()
            second = scheduled_favi_gr.tick(self.root, now=1001, deadline=2000)
        self.assertEqual(first["status"], "yielded")
        self.assertEqual(first["stage"], "bg_deadline")
        self.assertEqual(state_before, json.dumps({"generation": None, "next_run_at": 90000}))
        self.assertEqual(second["status"], "incomplete")
        self.assertEqual(len(calls), 1)

    def test_token_during_active_generation_reuses_journal(self):
        scans = []
        def scan(**kwargs):
            scans.append(kwargs["source_folder"])
            return {"status": "incomplete", "source_products": 100}
        with self._fake_scan(scan):
            first = scheduled_favi_gr.tick(self.root, now=1000, deadline=2000)
            with patch.dict(os.environ, {"FEED_FAVI_GR_REFRESH_TOKEN": "one-off-token-20261021-C"}):
                second = scheduled_favi_gr.tick(self.root, now=1010, deadline=2000)
                third = scheduled_favi_gr.tick(self.root, now=1020, deadline=2000)
        self.assertEqual(first["generation"], second["generation"])
        self.assertEqual(second["generation"], third["generation"])
        self.assertEqual(scans, [scans[0]] * 3)
        state = json.loads((self.root / "favi-gr-schedule.json").read_text())
        self.assertEqual(len(state["last_refresh_digest"]), 64)


if __name__ == "__main__":
    unittest.main()
