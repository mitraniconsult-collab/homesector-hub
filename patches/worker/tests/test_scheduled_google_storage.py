import json

from feeds.scheduled_google import reclaim_completed_runs


def test_reclaim_preserves_active_and_last_published(tmp_path):
    names = ['a' * 32, 'b' * 32, 'c' * 32, 'd' * 32]
    for name, finished in zip(names, (True, True, False, True)):
        path = tmp_path / 'google-bg-runs' / name / 'google-bg'
        path.mkdir(parents=True)
        (path / 'manifest.json').write_text(json.dumps({'finished': finished}))
    unrelated = tmp_path / 'google-bg-runs' / 'diagnostics'
    unrelated.mkdir()

    removed = reclaim_completed_runs(tmp_path, names[2], names[1])

    assert set(removed) == {names[0], names[3]}
    assert all((tmp_path / 'google-bg-runs' / name).exists() for name in names[1:3])
    assert unrelated.exists()
