"""Regression tests for resumable feed checkpoints on durable storage."""
import json
import os
import pytest
from feeds.durable_journal import DurableJournal

def test_requires_durable_storage_confirmation(tmp_path, monkeypatch):
    monkeypatch.delenv("FEED_DURABLE_STORAGE_CONFIRMED", raising=False)
    with pytest.raises(RuntimeError):
        DurableJournal(tmp_path)

def test_refuses_tmp_even_when_confirmed(monkeypatch):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    with pytest.raises(ValueError):
        DurableJournal("/tmp/homesector-feed")

def test_commit_and_resume_truncates_uncommitted_tail(tmp_path, monkeypatch):
    # Test temporary pytest directory as simulated mounted disk path. Constructor
    # refusal is separately tested; don't weaken the runtime guard.
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setattr("feeds.durable_journal.Path.resolve",
                        lambda self: self)
    # Use non-/tmp symbolic location to test journal algorithm.
    j = DurableJournal.__new__(DurableJournal)
    j.root = tmp_path
    j.records = tmp_path / "records.jsonl"
    j.manifest = tmp_path / "manifest.json"
    meta = j.commit("cursor-1", [{"id": "v1"}], 5)
    assert meta["items"] == 1
    with j.records.open("ab") as fh:
        fh.write(b'{"id":"UNCOMMITTED"}\n')
    resumed, rows = j.load()
    assert resumed["cursor"] == "cursor-1"
    assert rows == [{"id": "v1"}]
    assert j.records.stat().st_size == resumed["bytes"]

def test_fails_on_truncated_records(tmp_path):
    j = DurableJournal.__new__(DurableJournal)
    j.root = tmp_path
    j.records = tmp_path / "records.jsonl"
    j.manifest = tmp_path / "manifest.json"
    j.commit("cursor-1", [{"id": "v1"}], 5)
    j.records.write_bytes(b"")
    with pytest.raises(RuntimeError):
        j.load()
