"""Feed Manager endpoint smoke tests (no Shopify access required)."""
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from feeds.api import status
from feeds.targets import targets

class FeedStatusTests(unittest.TestCase):
    def test_thirteen_targets(self):
        self.assertEqual(len(targets()), 13)
        self.assertEqual(sum(1 for channel, _ in targets() if channel == "biano"), 1)

    def test_missing_token_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                status(authorization=None)
            self.assertEqual(ctx.exception.status_code, 503)

    def test_bad_token_is_rejected(self):
        with patch.dict(os.environ, {"HUB_WORKER_TOKEN": "test-secret"}):
            with self.assertRaises(HTTPException) as ctx:
                status(authorization="Bearer wrong")
            self.assertEqual(ctx.exception.status_code, 401)

    def test_status_does_not_fabricate_feeds(self):
        with patch.dict(os.environ, {"HUB_WORKER_TOKEN": "test-secret"}):
            data = status(authorization="Bearer test-secret")
            self.assertEqual(len(data["feeds"]), 13)
            self.assertTrue(all(f["xml_url"] is None for f in data["feeds"]))

if __name__ == "__main__":
    unittest.main()
