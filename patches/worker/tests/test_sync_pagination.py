"""Supplier count drift must not turn missing products into stopped items."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'easyrea'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync


class PaginationTests(unittest.TestCase):
    def fetch(self, pages, dry=False):
        supplier = sync.EasyRea()
        supplier.xsrf = 'test'
        supplier.s = Mock()
        responses = []
        for data in pages:
            response = Mock()
            response.json.return_value = data
            responses.append(response)
        supplier.s.post.side_effect = responses
        with patch.object(sync, 'DRY_RUN', dry), patch.object(sync.time, 'sleep'):
            result = supplier.fetch_all_products()
        return result, supplier.s.post.call_args_list

    def test_reported_incident_small_count_drift_after_confirmed_end(self):
        rows = [{'codeArticle': str(i), 'idTypeDispo': 1} for i in range(17839)]
        rows += rows[:252]  # 18091 rows, 17839 unique; supplier advertises 18103
        first = {'totalResults': 18103, 'results': rows}
        empty = {'totalResults': 18103, 'results': []}
        result, calls = self.fetch([first, empty, empty, empty])
        self.assertEqual(len(result), 17839)
        self.assertEqual([c.kwargs['json']['page'] for c in calls], [1, 2, 2, 2])
        self.assertNotIn('unseen-sku', result)

    def test_transient_empty_page_recovers_and_keeps_next_page(self):
        a = {'totalResults': 2, 'results': [{'codeArticle': 'A'}]}
        b = {'totalResults': 2, 'results': [{'codeArticle': 'B'}]}
        empty = {'totalResults': 2, 'results': []}
        result, calls = self.fetch([a, empty, b, empty])
        self.assertEqual(set(result), {'A', 'B'})
        self.assertEqual([c.kwargs['json']['page'] for c in calls], [1, 2, 2, 3])

    def test_large_gap_still_blocks_real_writes(self):
        a = {'totalResults': 100, 'results': [{'codeArticle': 'A'}]}
        empty = {'totalResults': 100, 'results': []}
        with self.assertRaisesRegex(RuntimeError, 'реалната синхронизация е спряна'):
            self.fetch([a, empty, empty, empty])

    def test_missing_results_is_not_a_valid_empty_page(self):
        with self.assertRaisesRegex(RuntimeError, 'Невалиден Easyrea'):
            self.fetch([{'totalResults': 0}])

    def test_repeated_page_blocks_even_if_count_matches(self):
        a = {'totalResults': 2, 'results': [{'codeArticle': 'A'}]}
        with self.assertRaisesRegex(RuntimeError, 'повтори страница'):
            self.fetch([a, a])

    def test_large_catalog_cannot_bypass_twenty_row_cap(self):
        a = {'totalResults': 100000, 'results': [{'codeArticle': str(i)} for i in range(99979)]}
        empty = {'totalResults': 100000, 'results': []}
        with self.assertRaisesRegex(RuntimeError, 'реалната синхронизация е спряна'):
            self.fetch([a, empty, empty, empty])


if __name__ == '__main__':
    unittest.main()
