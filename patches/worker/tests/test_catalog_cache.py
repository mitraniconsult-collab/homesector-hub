import gzip
import json
import time
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'easyrea'))
import catalog_cache


class CatalogCacheTests(unittest.TestCase):
    def payload(self, age=30):
        return {'version': 1, 'fetched_at': time.time() - age,
                'catalog': {'123': {'codeArticle': '123'}}, 'conflicts': [],
                'fiches': {'123': {'photoPrincipale': 'https://media.jja-sa.com/a.jpg'}}}

    def test_recent_snapshot_is_reused_without_easyrea_call(self):
        response = Mock(status_code=200, content=gzip.compress(json.dumps(self.payload()).encode()))
        with patch.dict('os.environ', {'HUB_WORKER_TOKEN': 'test'}), patch.object(catalog_cache.requests, 'get', return_value=response):
            self.assertIn('123', catalog_cache.load()['fiches'])

    def test_stale_snapshot_and_forced_refresh_are_not_reused(self):
        response = Mock(status_code=200, content=gzip.compress(json.dumps(self.payload(25 * 3600)).encode()))
        with patch.dict('os.environ', {'HUB_WORKER_TOKEN': 'test'}), patch.object(catalog_cache.requests, 'get', return_value=response) as get:
            self.assertIsNone(catalog_cache.load())
            self.assertIsNone(catalog_cache.load(force=True))
            self.assertEqual(get.call_count, 1)

    def test_complete_snapshot_is_compressed_on_save(self):
        response = Mock(status_code=200)
        with patch.dict('os.environ', {'HUB_WORKER_TOKEN': 'test'}), patch.object(catalog_cache.requests, 'put', return_value=response) as put:
            catalog_cache.save(self.payload())
            self.assertIn('123', json.loads(gzip.decompress(put.call_args.kwargs['data']))['catalog'])


if __name__ == '__main__':
    unittest.main()
