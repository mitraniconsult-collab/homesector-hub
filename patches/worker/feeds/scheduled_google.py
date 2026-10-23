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


def reclaim_completed_runs(root, active, previous):
    """Free older BG journals while preserving the current and last live run.

    An unfinished active journal is never removed. The public feed is an
    immutable Blob, but retaining its source run keeps local audit possible.
    """
    runs = root / 'google-bg-runs'
    if not runs.is_dir():
        return []
    protected = {active, previous}
    removed = []
    for folder in runs.iterdir():
        if (folder.name in protected or not folder.is_dir() or folder.is_symlink()
                or len(folder.name) != 32 or any(c not in '0123456789abcdef' for c in folder.name)):
            continue
        manifest = folder / 'google-bg' / 'manifest.json'
        if not manifest.is_file():
            continue
        try:
            complete = json.loads(manifest.read_text()).get('finished') is True
        except (OSError, ValueError):
            continue
        if complete:
            shutil.rmtree(folder)
            removed.append(folder.name)
    return removed


def reclaim_completed_market_runs(root):
    """Discard old complete market journals, preserving active and last runs."""
    removed = []
    for market in ('gr', 'ro', 'hu'):
        state_path = root / f'favi-{market}-schedule.json'
        runs = root / f'favi-{market}-runs'
        if not state_path.is_file() or not runs.is_dir():
            continue
        try:
            state = json.loads(state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        protected = {state.get('generation'), state.get('last_generation')}
        for folder in runs.iterdir():
            if (folder.name in protected or not folder.is_dir() or folder.is_symlink()
                    or len(folder.name) != 32
                    or any(c not in '0123456789abcdef' for c in folder.name)):
                continue
            manifest = folder / f'favi-{market}-source' / 'manifest.json'
            if not manifest.is_file():
                continue
            try:
                complete = json.loads(manifest.read_text(encoding='utf-8')).get('finished') is True
            except (OSError, ValueError):
                continue
            if complete:
                shutil.rmtree(folder)
                removed.append(market)
    return removed

def _error_detail(exc):
    return ' errno=' + str(exc.errno) if isinstance(exc, OSError) else ''


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
    # Respect a deliberate interval change immediately. The existing due time
    # was calculated under the old interval and must not start an unnecessary
    # hourly catalog while market URL scans need the shared worker.
    if (not state.get('generation') and state.get('last_success_at') is not None
            and state.get('scheduled_interval_seconds') != interval):
        state['next_run_at'] = state['last_success_at'] + interval
        state['scheduled_interval_seconds'] = interval
        save(path, state)
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
        removed = reclaim_completed_runs(root, generation, state.get('last_generation'))
        if removed:
            print('[feed-storage] removed_completed_bg_runs=' + str(len(removed)), flush=True)
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
            favi_phase = 'build'
            try:
                from .favi_bg_preview import create_preview
                favi = create_preview(root, source_folder=folder)
                if os.getenv('FEED_FAVI_BG_PREVIEW_PUBLISH') == 'yes':
                    favi_phase = 'publish'
                    from .favi_bg_delivery import publish_preview
                    print('[favi-bg-publication] ' + json.dumps(publish_preview(root, root), sort_keys=True), flush=True)
                print('[favi-preview] ' + json.dumps({
                    'generation': generation, 'xml_items': favi['xml_items'],
                    'blocked_missing_parent_group': favi['blocked_missing_parent_group'],
                    'skipped_no_checked_mapping': favi['skipped_no_checked_mapping'],
                    'blocked_legacy_id_migration': favi['blocked_legacy_id_migration'],
                    'id_migration_candidate_items': favi['id_migration_candidate_items'],
                    'id_migration_candidate_rejections': favi['id_migration_candidate_rejections'],
                    'serializer_rejections': favi['serializer_rejections'],
                    'categories_mapped': favi['categories_mapped'],
                    'top_unmapped_shopify_taxonomy': favi['top_unmapped_shopify_taxonomy'],
                }, sort_keys=True), flush=True)
            except Exception as exc:
                print('[favi-preview] FAILED phase=' + favi_phase +
                      ' type=' + type(exc).__name__, flush=True)
        completed = time.time() if real_clock else now
        state.update(generation=None, last_generation=generation, last_success_at=completed,
                     next_run_at=completed + interval, last_items=receipt['items'],
                     sha256=receipt['sha256'], receipt=receipt, last_error=None, retry_at=0,
                     scheduled_interval_seconds=interval)
        save(path, state)
        # The new run is now the public baseline; the previous published run
        # may be removed on the next tick, when this run is protected.
        return {**receipt, 'status': 'scheduled_snapshot_published', 'generation': generation,
                'next_run_at': state['next_run_at']}
    except Exception as exc:
        if isinstance(exc, OSError):
            print('[feed-storage] error errno=' + str(exc.errno) +
                  ' free_bytes=' + str(shutil.disk_usage(root).free), flush=True)
        # Keep the checkpoint and last public feed. Retry on the same cursor.
        state.update(last_error=type(exc).__name__, retry_at=now + 300, updated_at=now)
        save(path, state)
        raise


def _market_deadline(mount, now, sharing):
    bg_state = json.loads((Path(mount) / 'google-bg-schedule.json').read_text())
    due = [value for value in (bg_state.get('next_run_at'), bg_state.get('retry_at'))
           if isinstance(value, (int, float)) and value > now]
    # Keep two minutes for the next BG cycle. With two market scans enabled,
    # each gets a bounded slice so one storefront cannot starve the other.
    deadline = min(due) - 120 if due else now
    return min(deadline, now + 240) if sharing else deadline


def run(mount, should_stop):
    removed = reclaim_completed_market_runs(Path(mount))
    if removed:
        print('[feed-storage] removed_completed_market_runs=' +
              json.dumps({m: removed.count(m) for m in sorted(set(removed))}), flush=True)
    # Category-only revisions can be reviewed against the last complete BG
    # source without waiting for a fresh Shopify catalog cycle. This writes
    # private previews only; the public Google pointer is untouched.
    if os.getenv('FEED_FAVI_BG_PREVIEW') == 'yes' and not should_stop():
        favi_phase = 'build'
        try:
            root = Path(mount)
            state_path = root / 'google-bg-schedule.json'
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            generation = str(state.get('last_generation') or '')
            if len(generation) == 32 and all(c in '0123456789abcdef' for c in generation):
                folder = root / 'google-bg-runs' / generation / 'google-bg'
                if (folder / 'manifest.json').is_file():
                    from .favi_bg_preview import create_preview
                    report = create_preview(root, source_folder=folder)
                    if os.getenv('FEED_FAVI_BG_PREVIEW_PUBLISH') == 'yes':
                        favi_phase = 'publish'
                        from .favi_bg_delivery import publish_preview
                        print('[favi-bg-publication] ' + json.dumps(publish_preview(root, root), sort_keys=True), flush=True)
                    print('[favi-preview-rebuild] ' + json.dumps({
                        'source_generation': generation,
                        'xml_items': report['xml_items'],
                        'id_migration_candidate_items': report['id_migration_candidate_items'],
                        'skipped_no_checked_mapping': report['skipped_no_checked_mapping'],
                        'blocked_legacy_id_migration': report['blocked_legacy_id_migration'],
                        'serializer_rejections': report['serializer_rejections'],
                        'id_migration_candidate_rejections': report['id_migration_candidate_rejections'],
                        'categories_mapped': report['categories_mapped'],
                        'id_migration_xml_audit': report['id_migration_candidate_xml_audit'],
                        'id_migration_favi_audit': report['id_migration_candidate_favi_audit'],
                        'top_unmapped_shopify_taxonomy': report['top_unmapped_shopify_taxonomy'],
                    }, sort_keys=True), flush=True)
        except Exception as exc:
            print('[favi-preview-rebuild] FAILED phase=' + favi_phase +
                  ' type=' + type(exc).__name__ +
                  _error_detail(exc), flush=True)
    if os.getenv('FEED_FAVI_GR_PREVIEW_PUBLISH') == 'yes' and not should_stop():
        try:
            from .favi_gr_delivery import repair_published_report
            repair = repair_published_report()
            if repair['status'] == 'report_corrected':
                print('[favi-gr-report-repair] ' + json.dumps(repair, sort_keys=True), flush=True)
        except Exception as exc:
            print('[favi-gr-report-repair] FAILED type=' + type(exc).__name__ +
                  _error_detail(exc), flush=True)
    while not should_stop():
        try:
            result = tick(mount, should_stop=should_stop)
            print('[feed-schedule] ' + json.dumps(result, sort_keys=True), flush=True)
            if result['status'] == 'incomplete':
                continue
            # GR keeps its own durable generation and daily schedule; waiting
            # ticks do not repeat translations or storefront URL verification.
            if os.getenv('FEED_FAVI_GR_SCAN') == 'yes' and not should_stop():
                try:
                    from .scheduled_favi_gr import tick as tick_gr
                    now = time.time()
                    deadline = _market_deadline(
                        mount, now, os.getenv('FEED_FAVI_RO_SCAN') == 'yes')
                    gr = tick_gr(mount, should_stop=should_stop, deadline=deadline)
                    print('[favi-gr-scan] ' + json.dumps(gr, sort_keys=True), flush=True)
                except Exception as exc:
                    print('[favi-gr-scan] FAILED type=' + type(exc).__name__ +
                          _error_detail(exc) +
                          (' reason=' + str(exc)[:100] if isinstance(exc, RuntimeError) else ''),
                          flush=True)
            if os.getenv('FEED_FAVI_RO_SCAN') == 'yes' and not should_stop():
                try:
                    from .scheduled_favi_ro import tick as tick_ro
                    now = time.time()
                    deadline = _market_deadline(
                        mount, now, os.getenv('FEED_FAVI_GR_SCAN') == 'yes')
                    ro = tick_ro(mount, should_stop=should_stop, deadline=deadline)
                    print('[favi-ro-scan] ' + json.dumps(ro, sort_keys=True), flush=True)
                    if ro.get('status') == 'incomplete':
                        continue
                except Exception as exc:
                    print('[favi-ro-scan] FAILED type=' + type(exc).__name__ +
                          _error_detail(exc), flush=True)
            if os.getenv('FEED_FAVI_HU_SCAN') == 'yes' and not should_stop():
                try:
                    from .scheduled_favi_hu import tick as tick_hu
                    now = time.time()
                    sharing = (os.getenv('FEED_FAVI_GR_SCAN') == 'yes'
                               or os.getenv('FEED_FAVI_RO_SCAN') == 'yes')
                    deadline = _market_deadline(mount, now, sharing)
                    hu = tick_hu(mount, should_stop=should_stop, deadline=deadline)
                    print('[favi-hu-scan] ' + json.dumps(hu, sort_keys=True), flush=True)
                    if hu.get('status') == 'incomplete':
                        continue
                except Exception as exc:
                    print('[favi-hu-scan] FAILED type=' + type(exc).__name__ +
                          _error_detail(exc), flush=True)
        except Exception as exc:
            print('[feed-schedule] FAILED type=' + type(exc).__name__ +
                  _error_detail(exc), flush=True)
        for _ in range(6):
            if should_stop():
                return
            time.sleep(5)
