import json
import pytest
from feeds import snapshot_audit
from feeds.xml_export import generate
from test_xml_audit import good_row


def test_unmounted_or_unconfirmed_storage_cannot_be_reported(monkeypatch, tmp_path):
    monkeypatch.delenv("FEED_DURABLE_STORAGE_CONFIRMED", raising=False)
    monkeypatch.setenv("FEED_DURABLE_PATH", str(tmp_path))
    assert snapshot_audit.read_report() is None
    with pytest.raises(RuntimeError):
        snapshot_audit.audit_snapshots(tmp_path)
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setattr(snapshot_audit.os.path, "ismount", lambda path: False)
    assert snapshot_audit.read_report() is None
    with pytest.raises(RuntimeError):
        snapshot_audit.audit_snapshots(tmp_path)


def test_snapshot_quality_does_not_imply_release_readiness(monkeypatch, tmp_path):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setenv("FEED_DURABLE_PATH", str(tmp_path))
    monkeypatch.setattr(snapshot_audit.os.path, "ismount", lambda path: True)
    folder = tmp_path / "google-bg"
    folder.mkdir()
    xml = generate([good_row()], "BG", "google")
    (folder / "google-bg-unpublished.xml").write_bytes(xml)
    report = snapshot_audit.audit_snapshots(tmp_path)
    google, favi = report["feeds"]
    assert google["quality_passed"] and google["items"] == 1
    assert not google["release_ready"] and not google["destination_accepted"]
    assert not google["published"] and google["xml_url"] is None
    assert favi["status"] == "snapshot_missing"
    assert snapshot_audit.read_report() == report
    # Only report content is written; XML source remains byte-for-byte intact.
    assert (folder / "google-bg-unpublished.xml").read_bytes() == xml
    (tmp_path / "favi-bg-unpublished.xml").write_bytes(b"<broken>")
    assert snapshot_audit.audit_snapshots(tmp_path)["feeds"][1]["status"] == "invalid_xml"


def test_backorders_are_reported_as_blocking_without_modifying_xml(monkeypatch, tmp_path):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setattr(snapshot_audit.os.path, "ismount", lambda path: True)
    folder = tmp_path / "google-bg"
    folder.mkdir()
    row = {**good_row(), "available": False, "continue_selling": True}
    xml = generate([row], "BG", "google")
    (folder / "google-bg-unpublished.xml").write_bytes(xml)
    google = snapshot_audit.audit_snapshots(tmp_path)["feeds"][0]
    assert not google["quality_passed"]
    assert google["issues"] == {"invalid_backorder_availability_date": 1}
