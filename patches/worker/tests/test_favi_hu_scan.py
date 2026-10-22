"""HU source and URL stages resume without publishing partial output."""
import json
from pathlib import Path

import pytest

from feeds import favi_hu_finalize as finalize
from feeds import scheduled_favi_hu as schedule


class Journal:
    def __init__(self, root):
        self.root = Path(root)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"bytes": 1, "items": 1}))


def test_hu_url_throttle_reuses_saved_translation_batch(tmp_path, monkeypatch):
    product = {"id": "gid://shopify/Product/1", "handle": "chair",
               "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/2",
                                       "selectedOptions": [{"name": "Цвят", "value": "Бял"}]}]}}
    categories = {product["id"]: {"market": "HU", "verified": True,
                                   "path": "bútorok > székek > étkezőszékek"}}
    calls = {"translations": 0, "urls": 0}

    def translations(ids, **kwargs):
        calls["translations"] += 1
        return {ids[0]: {"HU": [{"key": "title", "value": "Szék"}]}}

    def urls(*args, **kwargs):
        calls["urls"] += 1
        if calls["urls"] == 1:
            raise RuntimeError("429")
        return {product["id"]: "https://homesector.hu/products/chair"}, {
            "checked": 1, "verified": 1, "reasons": {"verified": 1},
            "sample_handles": {}}

    monkeypatch.setattr(finalize, "fetch_translations", translations)
    monkeypatch.setattr(finalize, "verify_market_urls", urls)
    monkeypatch.setattr(finalize, "fetch_variant_translations",
                        lambda ids, *a, **kw: {ids[0]: []})
    journal = Journal(tmp_path)
    with pytest.raises(RuntimeError, match="429"):
        finalize.collect(journal, [product], categories, "shop.myshopify.com",
                         "token", float("inf"), lambda: False)
    result = finalize.collect(journal, [product], categories, "shop.myshopify.com",
                              "token", float("inf"), lambda: False)
    assert result["status"] == "ready"
    assert calls == {"translations": 1, "urls": 2}


def test_hu_completed_scan_stays_private_and_stale_scan_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setenv("FEED_FAVI_HU_PREVIEW_PUBLISH", "yes")
    monkeypatch.setattr(schedule.os.path, "ismount", lambda root: True)
    current = [1000.0]
    monkeypatch.setattr(schedule.time, "time", lambda: current[0])
    from feeds import favi_hu_catalog
    monkeypatch.setattr(favi_hu_catalog, "execute", lambda **kwargs: {
        "status": "unpublished_preview", "source_complete": True,
        "source_products": 19303, "xml_items": 2800, "sha256": "abc"})
    state_file = tmp_path / "favi-hu-schedule.json"
    state_file.write_text(json.dumps({"generation": "a" * 32, "started_at": 1000.0}))
    result = schedule.tick(tmp_path)
    assert result["status"] == "private_complete"
    assert result["items"] == 2800
    state_file.write_text(json.dumps({"generation": "b" * 32, "started_at": 1000.0}))
    current[0] = 1000 + schedule.MAX_SCAN_AGE_SECONDS + 1
    assert schedule.tick(tmp_path)["status"] == "stale_generation_rejected"
