"""HU preview keeps its pointer when a resumed source becomes stale."""
import json
from datetime import datetime, timezone

from feeds import scheduled_favi_hu as schedule


def test_stale_hu_scan_is_not_published(tmp_path, monkeypatch):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setenv("FEED_FAVI_HU_PREVIEW_PUBLISH", "yes")
    monkeypatch.setattr(schedule.os.path, "ismount", lambda root: True)
    times = [1000.0]
    monkeypatch.setattr(schedule.time, "time", lambda: times[0])

    def execute(**kwargs):
        return {"status": "unpublished_preview", "source_complete": True,
                "source_products": 19303, "xml_items": 300, "sha256": "abc"}

    from feeds import favi_hu_catalog
    monkeypatch.setattr(favi_hu_catalog, "execute", execute)
    state = {"generation": "a" * 32, "started_at": 1000.0}
    (tmp_path / "favi-hu-schedule.json").write_text(json.dumps(state))
    times[0] = 1000.0 + schedule.MAX_SCAN_AGE_SECONDS + 1
    result = schedule.tick(tmp_path)
    assert result["status"] == "stale_generation_rejected"
    saved = json.loads((tmp_path / "favi-hu-schedule.json").read_text())
    assert saved["generation"] is None


def test_hu_long_scan_with_recent_source_can_finish_privately(tmp_path, monkeypatch):
    monkeypatch.setenv("FEED_DURABLE_STORAGE_CONFIRMED", "yes")
    monkeypatch.setenv("FEED_FAVI_HU_PREVIEW_PUBLISH", "no")
    monkeypatch.setattr(schedule.os.path, "ismount", lambda root: True)
    now = 1000.0 + 8 * 3600
    monkeypatch.setattr(schedule.time, "time", lambda: now)
    from feeds import favi_hu_catalog
    monkeypatch.setattr(favi_hu_catalog, "execute", lambda **kw: {
        "status": "unpublished_preview", "source_complete": True,
        "source_snapshot_at": datetime.fromtimestamp(
            1000 + 4 * 3600, timezone.utc).isoformat(),
        "source_products": 19303, "xml_items": 300, "sha256": "abc"})
    (tmp_path / "favi-hu-schedule.json").write_text(json.dumps({
        "generation": "a" * 32, "started_at": 1000.0}))
    result = schedule.tick(tmp_path)
    assert result["status"] == "private_complete"
