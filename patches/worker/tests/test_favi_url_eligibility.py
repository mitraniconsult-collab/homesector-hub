import json
from types import SimpleNamespace

from feeds.favi_url_eligibility import reusable_urls


def test_reuses_only_same_market_product_and_current_handle(tmp_path):
    runs = tmp_path / "favi-gr-runs"
    old = runs / "old" / "favi-gr-source"
    current = runs / "new" / "favi-gr-source"
    old.mkdir(parents=True)
    current.mkdir(parents=True)
    (old / "manifest.json").write_text("{}")
    (old / "favi-gr-finalize-checkpoint.json").write_text(json.dumps({
        "auto_urls": {"p1": "https://homesector.gr/products/one",
                      "p2": "https://homesector.gr/products/old-two",
                      "p3": "https://homesector.ro/products/three"},
        "collection_urls": {"p1": "https://homesector.gr/collections/x/products/one",
                            "p2": "https://homesector.gr/collections/x/products/old-two"},
    }))
    products = [{"id": "p1", "handle": "one"},
                {"id": "p2", "handle": "new-two"},
                {"id": "p3", "handle": "three"}]
    direct, collection = reusable_urls(SimpleNamespace(root=current), products, {}, "GR")
    assert direct == {"p1": "https://homesector.gr/products/one"}
    assert collection == {"p1": "https://homesector.gr/collections/x/products/one"}
