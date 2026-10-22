"""429 must leave the current GR URL checkpoint batch unfinished."""
import importlib.util
import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from feeds.favi_gr_rate_limit import StorefrontRateLimited


class RateLimitCheckpointTests(unittest.TestCase):
    def test_rate_limit_preserves_unfinished_direct_url_batch(self):
        fake_collection = types.ModuleType("feeds.favi_gr_collection_urls")
        fake_url = types.ModuleType("feeds.favi_gr_urls")
        fake_auth = types.ModuleType("feeds.shopify_auth")
        fake_translation = types.ModuleType("feeds.shopify_translations")
        fake_collection.verify_collection_urls = lambda *a, **k: ({}, {})
        fake_auth.get_admin_token = lambda store: "token"
        fake_translation.fetch_translations = lambda ids, **k: {
            pid: {"GR": []} for pid in ids}
        fake_translation.fetch_variant_translations = lambda ids, market, **k: {
            vid: [] for vid in ids}
        calls = [0]

        def direct(products, categories, translated_map):
            calls[0] += 1
            if calls[0] == 1:
                raise StorefrontRateLimited("Greek storefront 429 cooldown")
            return {products[0]["id"]: "https://homesector.gr/products/chair"}, {
                "checked": 1, "verified": 1, "reasons": {"verified": 1},
                "sample_handles": {},
            }

        fake_url.verify_market_urls = direct
        with patch.dict(sys.modules, {
            "feeds.favi_gr_collection_urls": fake_collection,
            "feeds.favi_gr_urls": fake_url,
            "feeds.shopify_auth": fake_auth,
            "feeds.shopify_translations": fake_translation,
        }):
            spec = importlib.util.spec_from_file_location(
                "feeds._favi_gr_finalize_rate_limit_test",
                Path(__file__).resolve().parents[1] / "feeds" / "favi_gr_finalize.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                manifest = root / "manifest.json"
                manifest.write_text(json.dumps({
                    "bytes": 10, "items": 1, "products": 1}))
                journal = types.SimpleNamespace(root=root, manifest=manifest)
                product = {"id": "p1", "handle": "chair", "variants": {"nodes": []}}
                categories = {"p1": {"market": "GR", "path": "Chair"}}
                args = (journal, [product], categories, set(),
                        "shop.myshopify.com", "token", time.time() + 1000,
                        lambda: False)
                with self.assertRaises(StorefrontRateLimited):
                    module.collect(*args)
                checkpoint = json.loads((root /
                    "favi-gr-finalize-checkpoint.json").read_text())
                self.assertEqual(checkpoint["stage"], "direct_urls")
                self.assertEqual(checkpoint["next_index"], 0)
                self.assertEqual(checkpoint["url_check"]["checked"], 0)
                resumed = module.collect(*args)
                self.assertEqual(resumed["status"], "ready")
                self.assertEqual(resumed["url_check"]["checked"], 1)
                self.assertEqual(calls, [2])


if __name__ == "__main__":
    unittest.main()
