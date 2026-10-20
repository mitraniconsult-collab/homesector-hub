"""Translation fetch is read-only, batched, and refuses partial responses."""
import pytest
from feeds import shopify_translations as mod

def test_query_has_distinct_product_and_locale_aliases():
    query = mod.translations_query(2)
    assert "p0: product(id: $p0)" in query
    assert "p1: product(id: $p1)" in query
    assert 'ro: translations(locale: "ro")' in query
    assert 'gr: translations(locale: "el")' in query
    assert 'hu: translations(locale: "hu")' in query

def test_query_refuses_oversized_batch():
    with pytest.raises(ValueError):
        mod.translations_query(6)

def test_fetch_batches_and_preserves_only_source_values(monkeypatch):
    calls = []
    def fake_post(url, token, data):
        calls.append(data["variables"])
        records = {}
        for key, gid in data["variables"].items():
            records[key] = {"id": gid, "ro": [{"key": "title", "value": "Titlu"}],
                            "gr": [], "hu": []}
        return {"data": records}
    from feeds import markets_catalog
    monkeypatch.setattr(markets_catalog, "shopify_post", fake_post)
    ids = [f"gid://shopify/Product/{i}" for i in range(7)]
    result = mod.fetch_translations(ids, store="demo.myshopify.com", token="test")
    assert len(calls) == 2
    assert len(result) == 7
    assert result[ids[0]]["RO"][0]["value"] == "Titlu"
    assert result[ids[0]]["HU"] == []

def test_incomplete_response_fails(monkeypatch):
    from feeds import markets_catalog
    monkeypatch.setattr(markets_catalog, "shopify_post", lambda *a: {"data": {"p0": None}})
    with pytest.raises(RuntimeError):
        mod.fetch_translations(["gid://shopify/Product/1"],
                               store="demo.myshopify.com", token="test")
