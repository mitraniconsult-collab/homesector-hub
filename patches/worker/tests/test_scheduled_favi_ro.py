"""RO preview keeps its pointer when a resumed source becomes stale."""
import json
from datetime import datetime, timezone

from feeds import scheduled_favi_ro as schedule


def test_stale_ro_scan_is_not_published(tmp_path, monkeypatch):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setenv("FEED_FAVI_RO_PREVIEW_PUBLISH", "yes")
    monkeypatch.setattr(schedule.os.path, "ismount", lambda root: True)
    times = [1000.0]
    monkeypatch.setattr(schedule.time, "time", lambda: times[0])

    def execute(**kwargs):
        return {"status": "unpublished_preview", "source_complete": True,
                "source_products": 19303, "xml_items": 300, "sha256": "abc"}

    from feeds import favi_ro_catalog, favi_ro_delivery
    monkeypatch.setattr(favi_ro_catalog, "execute", execute)
    publishes = []
    monkeypatch.setattr(favi_ro_delivery, "publish_preview",
                        lambda *args: publishes.append(args))
    state = {"generation": "a" * 32, "started_at": 1000.0}
    (tmp_path / "favi-ro-schedule.json").write_text(json.dumps(state))
    times[0] = 1000.0 + schedule.MAX_SCAN_AGE_SECONDS + 1
    result = schedule.tick(tmp_path)
    assert result["status"] == "stale_generation_rejected"
    assert publishes == []
    saved = json.loads((tmp_path / "favi-ro-schedule.json").read_text())
    assert saved["generation"] is None


def test_ro_long_scan_with_recent_source_can_finish_privately(tmp_path, monkeypatch):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setenv("FEED_FAVI_RO_PREVIEW_PUBLISH", "no")
    monkeypatch.setattr(schedule.os.path, "ismount", lambda root: True)
    now = 1000.0 + 8 * 3600
    monkeypatch.setattr(schedule.time, "time", lambda: now)
    from feeds import favi_ro_catalog
    monkeypatch.setattr(favi_ro_catalog, "execute", lambda **kw: {
        "status": "unpublished_preview", "source_complete": True,
        "source_snapshot_at": datetime.fromtimestamp(
            1000 + 4 * 3600, timezone.utc).isoformat(),
        "source_products": 19303, "xml_items": 300, "sha256": "abc"})
    (tmp_path / "favi-ro-schedule.json").write_text(json.dumps({
        "generation": "a" * 32, "started_at": 1000.0}))
    result = schedule.tick(tmp_path)
    assert result["status"] == "private_complete"
