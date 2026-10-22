import importlib.util
import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class StagedFinalizeTests(unittest.TestCase):
    def test_resume_skips_completed_translation_and_url_batches(self):
        calls = {"translations": [], "direct": [], "collections": [], "variants": []}
        fake_collection = types.ModuleType("feeds.favi_gr_collection_urls")
        fake_url = types.ModuleType("feeds.favi_gr_urls")
        fake_auth = types.ModuleType("feeds.shopify_auth")
        fake_translation = types.ModuleType("feeds.shopify_translations")

        def translations(ids, **kwargs):
            calls["translations"].extend(ids)
            return {pid: {"GR": [{"key": "title", "value": "τίτλος"}]} for pid in ids}

        def direct(products, categories, translated_map):
            calls["direct"].extend(p["id"] for p in products)
            valid = {p["id"]: "https://homesector.gr/products/" + p["handle"]
                     for p in products if p["id"] != "p2"}
            return valid, {"checked": len(products), "verified": len(valid),
                           "reasons": {"verified": len(valid),
                                       "non_200": len(products) - len(valid)},
                           "sample_handles": {}}

        def collections(products, already_verified, store, token):
            calls["collections"].extend(p["id"] for p in products)
            return {p["id"]: "https://homesector.gr/collections/x/products/" +
                    p["handle"] for p in products}, {
                "checked": len(products), "verified": len(products),
                "without_collection": 0,
            }

        def variants(ids, market, **kwargs):
            calls["variants"].extend(ids)
            return {vid: [] for vid in ids}

        fake_collection.verify_collection_urls = collections
        fake_url.verify_market_urls = direct
        fake_auth.get_admin_token = lambda store: "token"
        fake_translation.fetch_translations = translations
        fake_translation.fetch_variant_translations = variants
        with patch.dict(sys.modules, {
            "feeds.favi_gr_collection_urls": fake_collection,
            "feeds.favi_gr_urls": fake_url,
            "feeds.shopify_auth": fake_auth,
            "feeds.shopify_translations": fake_translation,
        }):
            spec = importlib.util.spec_from_file_location(
                "feeds._favi_gr_finalize_under_test",
                Path(__file__).resolve().parents[1] / "feeds" / "favi_gr_finalize.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                manifest = root / "manifest.json"
                manifest.write_text(json.dumps({"bytes": 123, "items": 3, "products": 3}))
                journal = types.SimpleNamespace(root=root, manifest=manifest)
                products = [
                    {"id": "p" + str(i), "handle": "handle-" + str(i),
                     "variants": {"nodes": [{
                         "id": "v" + str(i),
                         "selectedOptions": [{"name": "Color"}],
                     }]}}
                    for i in range(1, 4)
                ]
                categories = {p["id"]: {"market": "GR", "path": "X"}
                              for p in products}
                counter = [0]
                def pause_after_one_direct():
                    counter[0] += 1
                    return counter[0] > 5
                with patch.object(module, "TRANSLATION_BATCH", 1), \
                     patch.object(module, "URL_BATCH", 1), \
                     patch.object(module, "VARIANT_BATCH", 1):
                    first = module.collect(
                        journal, products, categories, set(), "shop.myshopify.com",
                        "token", time.time() + 1000, pause_after_one_direct)
                    self.assertEqual(first["status"], "yielded")
                    self.assertEqual(first["stage"], "direct_urls")
                    self.assertEqual(len(calls["direct"]), 1)
                    completed = module.collect(
                        journal, products, categories, set(), "shop.myshopify.com",
                        "token", time.time() + 1000, lambda: False)
                    repeated = module.collect(
                        journal, products, categories, set(), "shop.myshopify.com",
                        "token", time.time() + 1000, lambda: False)
                self.assertEqual(completed["status"], "ready")
                self.assertEqual(repeated["status"], "ready")
                self.assertEqual(calls["translations"], ["p1", "p2", "p3"])
                self.assertEqual(calls["direct"], ["p1", "p2", "p3"])
                self.assertEqual(calls["collections"], ["p2"])
                self.assertEqual(calls["variants"], ["v1", "v2", "v3"])
                mixed = [
                    {"id": "p1", "variants": {"nodes": [
                        {"id": "aroma", "selectedOptions": [{"name": "Аромат", "value": "Роза"}]},
                        {"id": "size", "selectedOptions": [{"name": "Размер", "value": "120x170 cm"}]},
                    ]}},
                    {"id": "p2", "variants": {"nodes": [
                        {"id": "unverified", "selectedOptions": [{"name": "Аромат"}]},
                    ]}},
                ]
                self.assertEqual(module._variant_ids(mixed, {"p1"}), ["aroma", "size"])


if __name__ == "__main__":
    unittest.main()
