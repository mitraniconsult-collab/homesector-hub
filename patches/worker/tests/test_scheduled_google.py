import json
from pathlib import Path
import pytest
from feeds import scheduled_google as job
from feeds.xml_export import generate
from test_xml_audit import good_row


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setenv('FEED_DURABLE_STORAGE_CONFIRMED', 'yes')
    monkeypatch.setenv('FEED_GOOGLE_REGENERATE_SECONDS', '3600')
    monkeypatch.setattr(job.os.path, 'ismount', lambda path: True)
    calls = []
    def execute(**options):
        calls.append(('catalog', str(options['root'])))
        folder = Path(options['root']) / 'google-bg'
        folder.mkdir(parents=True, exist_ok=True)
        return {'status': 'completed', 'items': 1}
    def refresh(root, source_folder):
        calls.append(('refresh', str(source_folder)))
        (source_folder / 'google-bg-corrected-unpublished.xml').write_bytes(generate([good_row()], 'BG', 'google'))
    def publish(root, source_folder):
        calls.append(('publish', str(source_folder)))
        return {'status': 'comparison_snapshot_uploaded', 'items': 1, 'sha256': 'abc'}
    monkeypatch.setattr(job, 'execute', execute)
    monkeypatch.setattr(job, 'refresh', refresh)
    monkeypatch.setattr(job, 'publish_comparison', publish)
    return tmp_path, calls


def test_hourly_cycle_builds_new_generation_and_waits(runtime):
    root, calls = runtime
    first = job.tick(root, now=100)
    assert first['status'] == 'scheduled_snapshot_published'
    assert [c[0] for c in calls] == ['catalog', 'refresh', 'publish']
    assert job.tick(root, now=3699)['status'] == 'waiting'
    assert len(calls) == 3
    second = job.tick(root, now=3700)
    assert second['generation'] != first['generation']


def test_incomplete_catalog_resumes_same_generation_without_publishing(runtime, monkeypatch):
    root, calls = runtime
    original = job.execute
    monkeypatch.setattr(job, 'execute', lambda **kw: {'status': 'incomplete', 'items': 1})
    job.tick(root, now=100)
    generation = json.loads((root / 'google-bg-schedule.json').read_text())['generation']
    assert not calls
    monkeypatch.setattr(job, 'execute', original)
    result = job.tick(root, now=101)
    assert result['generation'] == generation


def test_failed_publication_keeps_last_success_and_retries_same_generation(runtime, monkeypatch):
    root, calls = runtime
    first = job.tick(root, now=100)
    def fail(*args, **kwargs): raise RuntimeError('storage unavailable')
    monkeypatch.setattr(job, 'publish_comparison', fail)
    with pytest.raises(RuntimeError): job.tick(root, now=3700)
    state = json.loads((root / 'google-bg-schedule.json').read_text())
    assert state['last_generation'] == first['generation']
    assert state['generation'] != first['generation']
    assert state['last_success_at'] == 100
    assert job.tick(root, now=3701)['status'] == 'retry_wait'


def test_large_catalog_decline_does_not_publish(runtime):
    root, calls = runtime
    folder = root / 'google-bg'
    folder.mkdir()
    (folder / 'manifest.json').write_text(json.dumps({'items': 100}))
    with pytest.raises(RuntimeError, match='declined'): job.tick(root, now=100)
    assert 'publish' not in [c[0] for c in calls]


def test_shutdown_before_publication_keeps_existing_feed(runtime):
    root, calls = runtime
    result = job.tick(root, now=100, should_stop=lambda: True)
    assert result['status'] == 'interrupted'
    assert [c[0] for c in calls] == ['catalog']


def test_invalid_interval_does_not_start_catalog(runtime, monkeypatch):
    root, calls = runtime
    monkeypatch.setenv('FEED_GOOGLE_REGENERATE_SECONDS', '1')
    with pytest.raises(ValueError): job.tick(root)
    assert not calls
