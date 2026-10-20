"""Unit tests: bounded read-only batch job and crash recovery mechanics."""
import json
from feeds import batch_job

def test_bounded_job_does_not_publish_and_saves_page(monkeypatch, tmp_path):
    class Journal:
        def __init__(self, root):
            self.manifest = tmp_path / "manifest.json"
            self.root = tmp_path
            self.pages = []
        def append_page(self, cursor, rows, products, finished=False):
            self.pages.append((cursor, rows, products, finished))
            return {"products": products, "items": len(rows), "finished": finished}
    journals = []
    def make_journal(root):
        result = Journal(root)
        journals.append(result)
        return result
    monkeypatch.setattr(batch_job, "DurableJournal", make_journal)
    monkeypatch.setattr(batch_job, "post_graphql", lambda *args: {
        "products": {"nodes": [{"id": "gid://shopify/Product/12",
                                 "status": "DRAFT", "published_BG": False,
                                 "variants": {"pageInfo": {"hasNextPage": False},
                                              "nodes": []}}],
                     "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}})
    report = batch_job.execute(batch_limit=1, root="/durable", store="test.myshopify.com", token="t")
    assert report == {"status": "incomplete", "products": 1, "items": 0,
                      "cursor_saved": True, "published": False}
    assert journals[0].pages == [("c1", [], 1, False)]

def test_page_limit_rejected():
    for limit in (-1, 0, 1001):
        try:
            batch_job.execute(batch_limit=limit)
        except ValueError:
            continue
        raise AssertionError("Unbounded jobs must be rejected")
