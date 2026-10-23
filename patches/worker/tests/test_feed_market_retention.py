"""Completed market journals can be reclaimed without losing resume state."""
import json
import tempfile
import unittest
from pathlib import Path

from feeds.scheduled_google import reclaim_completed_market_runs


class MarketRetentionTest(unittest.TestCase):
    def test_preserves_active_last_and_unfinished_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active, last, old, unfinished = ('a' * 32, 'b' * 32,
                                             'c' * 32, 'd' * 32)
            (root / 'favi-hu-schedule.json').write_text(json.dumps({
                'generation': active, 'last_generation': last}))
            for run, complete in ((active, True), (last, True),
                                  (old, True), (unfinished, False)):
                folder = root / 'favi-hu-runs' / run / 'favi-hu-source'
                folder.mkdir(parents=True)
                (folder / 'manifest.json').write_text(json.dumps({
                    'finished': complete}))
            self.assertEqual(reclaim_completed_market_runs(root), ['hu'])
            for run in (active, last, unfinished):
                self.assertTrue((root / 'favi-hu-runs' / run).exists())
            self.assertFalse((root / 'favi-hu-runs' / old).exists())


if __name__ == '__main__':
    unittest.main()
