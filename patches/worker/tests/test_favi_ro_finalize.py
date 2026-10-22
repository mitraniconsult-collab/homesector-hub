"""RO batches resume after storefront throttling without repeating saved work."""
import json
from pathlib import Path

import pytest

from feeds import favi_ro_finalize as finalize


class Journal:
    def __init__(self, root):
        self.root = Path(root)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"bytes": 1, "items": 1}))


def test_ro_url_throttle_keeps_translations_and_cursor(tmp_path, monkeypatch):
    product = {"id": "gid://shopify/Product/1", "handle": "one",
               "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/2",
                                       "selectedOptions": [{"name": "Цвят", "value": "Бял"}]}]}}
    categories = {product["id"]: {"market": "RO", "verified": True,
                                   "path": "decorațiuni > oglinzi"}}
    calls = {"translations": 0, "urls": 0}

    def translations(ids, **kwargs):
        calls["translations"] += 1
        return {ids[0]: {"RO": [{"key": "title", "value": "Oglindă"}]}}

    def urls(*args, **kwargs):
        calls["urls"] += 1
        if calls["urls"] == 1:
            raise RuntimeError("429")
        return {product["id"]: "https://homesector.ro/products/one"}, {
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
    assert result["url_check"]["checked"] == 1
    assert calls == {"translations": 1, "urls": 2}


def test_incomplete_ro_translation_batch_retries_same_batch(tmp_path, monkeypatch):
    product = {"id": "p1", "handle": "one", "variants": {"nodes": []}}
    categories = {"p1": {"market": "RO", "path": "oglinzi"}}
    calls = []

    def translations(ids, **kwargs):
        calls.append(ids)
        return {} if len(calls) == 1 else {"p1": {"RO": []}}

    monkeypatch.setattr(finalize, "fetch_translations", translations)
    monkeypatch.setattr(finalize, "verify_market_urls", lambda *a, **kw: (
        {"p1": "https://homesector.ro/products/one"},
        {"checked": 1, "verified": 1, "reasons": {"verified": 1}, "sample_handles": {}}))
    with pytest.raises(RuntimeError, match="Incomplete RO translation batch"):
        finalize.collect(Journal(tmp_path), [product], categories,
                         "shop.myshopify.com", "token", float("inf"), lambda: False)
    result = finalize.collect(Journal(tmp_path), [product], categories,
                              "shop.myshopify.com", "token", float("inf"), lambda: False)
    assert result["status"] == "ready"
    assert calls == [["p1"], ["p1"]]
