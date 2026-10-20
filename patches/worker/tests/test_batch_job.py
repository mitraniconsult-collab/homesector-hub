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


def test_http_200_throttle_retries_without_advancing_cursor(monkeypatch):
    answers = iter([{"errors": [{"extensions": {"code": "THROTTLED"}}],
                     "extensions": {"cost": {"requestedQueryCost": 100,
                       "throttleStatus": {"currentlyAvailable": 0, "restoreRate": 50}}}},
                    {"data": {"ok": True}}])
    calls, delays = [], []
    def post(*args):
        calls.append(args[-1]["variables"])
        return next(answers)
    monkeypatch.setattr(batch_job, "shopify_post", post)
    monkeypatch.setattr(batch_job.time, "sleep", delays.append)
    assert batch_job.post_graphql("url", "t", "q", {"cursor": "c1"}) == {"ok": True}
    assert calls == [{"cursor": "c1"}, {"cursor": "c1"}] and delays == [2.25]
