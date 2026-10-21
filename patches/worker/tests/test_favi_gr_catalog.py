"""The Greek catalog scan resumes from the last complete Shopify page."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from feeds import favi_gr_catalog
from feeds.markets_catalog import catalog_query


def test_greek_scan_resumes_without_repeating_first_page(monkeypatch):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    query = catalog_query(gr_only=True)
    assert "published_GR" in query and "price_GR" in query
    assert "price_BG" not in query
    pages = [
        {"products": {"nodes": [{"id": "gid://shopify/Product/1",
                                  "variants": {"nodes": [], "pageInfo": {"hasNextPage": False}}}],
                      "pageInfo": {"hasNextPage": True, "endCursor": "next"}}},
        {"products": {"nodes": [{"id": "gid://shopify/Product/2",
                                  "variants": {"nodes": [], "pageInfo": {"hasNextPage": False}}}],
                      "pageInfo": {"hasNextPage": False, "endCursor": "last"}}},
    ]
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as root:
        with patch.object(favi_gr_catalog, "get_admin_token", return_value="test"), \
                patch.object(favi_gr_catalog, "post_graphql", side_effect=pages) as post, \
                patch.object(favi_gr_catalog, "finalize", return_value={"status": "private_complete"}):
            first = favi_gr_catalog.execute(batch_limit=1, root=root, store="test.myshopify.com")
            second = favi_gr_catalog.execute(batch_limit=1, root=root, store="test.myshopify.com")
        assert first["status"] == "incomplete" and first["source_products"] == 1
        assert second["status"] == "private_complete"
        assert post.call_args_list[0].args[3] == {"cursor": None}
        assert post.call_args_list[1].args[3] == {"cursor": "next"}
        manifest, rows = favi_gr_catalog.DurableJournal(
            Path(root) / "favi-gr-source").load()
        assert manifest["finished"] and len(rows) == 2
