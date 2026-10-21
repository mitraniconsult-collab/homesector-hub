"""Restartable hourly catalog generations on the existing mounted worker.

Every generation has its own journal. The public pointer changes only after a
complete catalog, fresh inventory read, and verified immutable Blob uploads.
"""
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from .batch_job import execute
from .availability_refresh import refresh
from .blob_delivery import publish_comparison
from .xml_audit import validate_xml


def save(path, state):
    temp = path.with_suffix('.tmp')
    with temp.open('w') as file:
        json.dump(state, file)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, path)


def tick(mount, should_stop=lambda: False, now=None):
    root = Path(mount).resolve()
    if os.getenv('FEED_DURABLE_STORAGE_CONFIRMED') != 'yes' or not os.path.ismount(root):
        raise RuntimeError('Confirmed mounted feed storage required')
    interval = int(os.getenv('FEED_GOOGLE_REGENERATE_SECONDS', '3600'))
    if not 900 <= interval <= 86400:
        raise ValueError('Google regeneration interval must be 900..86400 seconds')
    real_clock = now is None
    now = time.time() if real_clock else now
    path = root / 'google-bg-schedule.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    if now < state.get('retry_at', 0):
        return {'status': 'retry_wait', 'retry_at': state['retry_at']}
    if not state.get('generation'):
        if now < state.get('next_run_at', 0):
            return {'status': 'waiting', 'next_run_at': state['next_run_at']}
        state.update(generation=uuid.uuid4().hex, started_at=now)
        save(path, state)
    generation = state['generation']
    if len(generation) != 32 or any(c not in '0123456789abcdef' for c in generation):
        raise ValueError('Invalid scheduled generation ID')
    run_root = root / 'google-bg-runs' / generation
    folder = run_root / 'google-bg'
    try:
        result = execute(batch_limit=10, root=run_root, bg_only=True, should_stop=should_stop)
        state.update(progress=result, updated_at=now)
        save(path, state)
        if result['status'] != 'completed' or should_stop():
            return {**result, 'status': 'interrupted' if should_stop() else 'incomplete', 'generation': generation}
        # Inventory and dates may have changed while paginating the catalog.
        refresh(root, source_folder=folder)
        if should_stop():
            return {'status': 'interrupted_before_publication', 'generation': generation}
        xml = (folder / 'google-bg-corrected-unpublished.xml').read_bytes()
        audit = validate_xml(xml, 'BG', max_issues=0)
        initial_manifest = root / 'google-bg/manifest.json'
        baseline = state.get('last_items')
        if baseline is None and initial_manifest.exists():
            baseline = json.loads(initial_manifest.read_text())['items']
        if (not audit['items'] or audit['unique_ids'] != audit['items']
                or baseline and audit['items'] < baseline * .8):
            raise RuntimeError('Catalog empty, duplicate, or declined by more than 20 percent')
        # Missing descriptions stay visible; no quantity-zero CONTINUE filter.
        receipt = publish_comparison(root, source_folder=folder)
        # FAVI stays private until its ID and category gates pass. A preview
        # failure cannot stall an otherwise successful Google publication.
        if os.getenv('FEED_FAVI_BG_PREVIEW') == 'yes':
            try:
                from .favi_bg_preview import create_preview
                favi = create_preview(root, source_folder=folder)
                print('[favi-preview] ' + json.dumps({
                    'generation': generation, 'xml_items': favi['xml_items'],
                    'blocked_missing_parent_group': favi['blocked_missing_parent_group'],
                }, sort_keys=True), flush=True)
            except Exception as exc:
                print('[favi-preview] FAILED type=' + type(exc).__name__, flush=True)
        completed = time.time() if real_clock else now
        state.update(generation=None, last_generation=generation, last_success_at=completed,
                     next_run_at=completed + interval, last_items=receipt['items'],
                     sha256=receipt['sha256'], receipt=receipt, last_error=None, retry_at=0)
        save(path, state)
        # Keep three complete local runs plus any interrupted active generation.
        runs = sorted((root / 'google-bg-runs').iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in runs[3:]:
            if old.is_dir() and not old.is_symlink() and old.name != generation:
                shutil.rmtree(old)
        return {**receipt, 'status': 'scheduled_snapshot_published', 'generation': generation,
                'next_run_at': state['next_run_at']}
    except Exception as exc:
        # Keep the checkpoint and last public feed. Retry on the same cursor.
        state.update(last_error=type(exc).__name__, retry_at=now + 300, updated_at=now)
        save(path, state)
        raise


def run(mount, should_stop):
    gr_complete = False
    while not should_stop():
        try:
            result = tick(mount, should_stop=should_stop)
            print('[feed-schedule] ' + json.dumps(result, sort_keys=True), flush=True)
            if result['status'] == 'incomplete':
                continue
            # Scan the Greek source catalog in bounded batches while BG waits.
            # It writes a private quality report only, with no external URL.
            if (os.getenv('FEED_FAVI_GR_SCAN') == 'yes' and not gr_complete
                    and not should_stop()):
                try:
                    from .favi_gr_catalog import execute as scan_gr
                    gr = scan_gr(batch_limit=int(os.getenv('FEED_GR_PAGE_LIMIT', '100')),
                                 root=mount, should_stop=should_stop)
                    gr_complete = gr.get('source_complete', False)
                    print('[favi-gr-scan] ' + json.dumps(gr, sort_keys=True), flush=True)
                    if gr.get('status') == 'incomplete':
                        continue
                except Exception as exc:
                    print('[favi-gr-scan] FAILED type=' + type(exc).__name__, flush=True)
        except Exception as exc:
            print('[feed-schedule] FAILED type=' + type(exc).__name__, flush=True)
        for _ in range(6):
            if should_stop():
                return
            time.sleep(5)
