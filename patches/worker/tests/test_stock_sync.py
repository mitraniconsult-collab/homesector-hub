import csv
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'easyrea'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sync
from stock_rules import decide, product_date
from job_store import JobStore

TODAY = date(2026, 10, 4)


def variant(sku='A', quantity=0, policy='DENY', arrival=None):
    return dict(sku=sku, variant_id='v'+sku, product_id='p', quantity=quantity,
                tracked=True, status='ACTIVE', vendor='atmosphera',
                inventory_policy=policy, variant_date=arrival, product_date=arrival,
                template_suffix='preorder' if arrival else '', variant_count=1)


class FakeShopify:
    def __init__(self, variants):
        self.variants = variants
        self.calls = []

    def fetch_all_variants(self):
        return self.variants

    def set_variant_policy(self, product, variant, policy):
        self.calls.append(('policy', variant, policy))
        next(v for v in self.variants if v['variant_id'] == variant)['inventory_policy'] = policy

    def set_metafield_date(self, owner, value):
        self.calls.append(('date', owner, value))
        for v in self.variants:
            if owner == v['variant_id']:
                v['variant_date'] = value
            if owner == v['product_id']:
                v['product_date'] = value

    def set_template(self, product, value):
        self.calls.append(('template', product, value))
        for v in self.variants:
            if v['product_id'] == product:
                v['template_suffix'] = value


class BusinessRules(unittest.TestCase):
    def test_incomplete_catalogue_allows_diagnostics_but_blocks_real_run(self):
        for dry in (True, False):
            supplier = object.__new__(sync.EasyRea)
            supplier.xsrf = 'test'
            supplier.s = Mock()
            response = Mock()
            response.json.side_effect = [
                {'totalResults': 10, 'results': [{'codeArticle': 'A', 'idTypeDispo': 1}]},
                {'totalResults': 10, 'results': []},
                {'totalResults': 10, 'results': []},
                {'totalResults': 10, 'results': []},
            ]
            supplier.s.post.return_value = response
            with patch.object(sync, 'DRY_RUN', dry), patch.object(sync.time, 'sleep'):
                if dry:
                    self.assertIn('A', supplier.fetch_all_products())
                else:
                    with self.assertRaisesRegex(RuntimeError, 'реалната синхронизация е спряна'):
                        supplier.fetch_all_products()

    def test_missing_skus_do_not_block_confirmed_variants_or_change_unknown_siblings(self):
        vs = [variant(code, policy='DENY', arrival='2099-12-16')
              for code in ('A', 'C', 'D', 'Z', 'B', 'E', 'F', 'G', 'H', 'I', '')]
        for v in vs:
            v['variant_count'] = len(vs)
        catalog = {code: {'idTypeDispo': 1} for code in ('A', 'C', 'D')}
        catalog['Z'] = {'idTypeDispo': 0}  # unknown must not become stopped
        sh = FakeShopify(vs)
        supplier = Mock()
        supplier.fetch_all_products.return_value = catalog
        with tempfile.TemporaryDirectory() as tmp, patch.object(sync, 'DRY_RUN', False), \
             patch.object(sync, 'REPORT_FILE', str(Path(tmp) / 'report.csv')), \
             patch.object(sync.runtime, 'require_env'), patch.object(sync.runtime, 'force', return_value=False), \
             patch.object(sync, 'EasyRea', return_value=supplier), patch.object(sync, 'Shopify', return_value=sh):
            sync.main()
            with Path(sync.REPORT_FILE).open(encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), len(vs))
        self.assertEqual(sum(r['applied'] == 'review' for r in rows), 8)
        self.assertEqual({call[1] for call in sh.calls}, {'vA', 'vC', 'vD'})
        for v in vs:
            self.assertEqual(v['product_date'], '2099-12-16')
            self.assertEqual(v['quantity'], 0)
            if v['sku'] not in ('A', 'C', 'D'):
                self.assertEqual(v['inventory_policy'], 'DENY')
                self.assertEqual(v['variant_date'], '2099-12-16')

    def test_unknown_supplier_status_spike_still_blocks_real_run(self):
        vs = [variant('A'), variant('B'), variant('C')]
        catalog = {'A': {'idTypeDispo': 1}, 'B': {'idTypeDispo': 0}}
        entries = [e for group in sync.build_plan(vs, catalog).values() for e in group]
        with patch.object(sync.runtime, 'force', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'Над 25% непознати статуси'):
                sync.validate_plan(entries, dry_run=False)
        counts = sync.validate_plan(entries, dry_run=True)
        self.assertEqual(counts['missing_supplier'], 1)
        self.assertEqual(counts['unknown_status'], 1)

    def test_untracked_matched_variants_do_not_dilute_unknown_status_guard(self):
        vs = [variant('A'), variant('B')] + [dict(variant(str(i)), tracked=False) for i in range(10)]
        catalog = {v['sku']: {'idTypeDispo': 1} for v in vs}
        catalog['B'] = {'idTypeDispo': 0}
        entries = [e for group in sync.build_plan(vs, catalog).values() for e in group]
        with patch.object(sync.runtime, 'force', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'Над 25% непознати статуси'):
                sync.validate_plan(entries, dry_run=False)

    def test_no_confirmed_variant_blocks_real_run(self):
        entries = [e for group in sync.build_plan([variant('A')], {}).values() for e in group]
        with self.assertRaisesRegex(RuntimeError, 'Няма потвърдени варианти'):
            sync.validate_plan(entries, dry_run=False)

    def test_supplier_stock_enables_oversell_and_clears_date_for_all_quantities(self):
        for qty in (-3, 0, 4):
            d = decide({'idTypeDispo': 1}, qty, today=TODAY)
            self.assertEqual((d.policy, d.arrival), ('CONTINUE', None))

    def test_arriving_with_local_stock_sells_only_local_stock(self):
        d = decide({'idTypeDispo': 2, 'dateArrivage': '2026-12-16'}, 3, today=TODAY)
        self.assertEqual((d.policy, d.arrival), ('DENY', None))

    def test_arriving_without_local_stock_accepts_preorders(self):
        for qty in (0, -2):
            d = decide({'idTypeDispo': 2, 'dateArrivage': '2026-12-16T00:00:00Z'}, qty, today=TODAY)
            self.assertEqual((d.policy, d.arrival), ('CONTINUE', '2026-12-16'))

    def test_invalid_missing_past_dates_stop_preorders(self):
        for value in (None, '', '16/12/2026', '2026-02-30', '2026-10-03'):
            d = decide({'idTypeDispo': 2, 'dateArrivage': value}, 0, today=TODAY)
            self.assertEqual((d.policy, d.arrival), ('DENY', None))

    def test_stopped_never_oversells_even_with_local_stock(self):
        for qty in (4, 0, -2):
            d = decide({'idTypeDispo': 99, 'availabilityLabel': 'Product stopped'}, qty, today=TODAY)
            self.assertEqual((d.policy, d.arrival), ('DENY', None))

    def test_confirmed_stopped_ids_and_unknown_status_are_distinct(self):
        self.assertEqual(decide({'idTypeDispo': 99}, 1, stopped_ids={'99'}).policy, 'DENY')
        self.assertIsNone(decide({'idTypeDispo': 99}, 1).policy)
        self.assertIsNone(decide(None, 1).policy)
        self.assertIsNone(decide({'idTypeDispo': 1}, None).policy)

    def test_conflicting_variant_dates_do_not_overwrite_product_with_one_colour(self):
        ds = [decide({'idTypeDispo': 2, 'dateArrivage': dt}, 0, today=TODAY)
              for dt in ('2026-12-16', '2026-12-20')]
        self.assertEqual(product_date(ds)[:2], (True, None))
        self.assertEqual(product_date(ds, complete=False)[:2], (False, None))

    def test_unknown_sibling_preserves_product_metadata(self):
        ds = [decide(None, 0), decide({'idTypeDispo': 1}, 1)]
        self.assertEqual(product_date(ds)[:2], (False, None))

    def test_supplier_scope_and_exact_sku_matching(self):
        vs = [variant('A'), variant('AA'), dict(variant('B'), vendor='OTHER')]
        groups = sync.build_plan(vs, {'A': {'idTypeDispo': 1}})
        self.assertEqual(len(groups['p']), 2)
        self.assertEqual([d.action for _, _, d in groups['p']], ['IN_STOCK', 'REVIEW'])

    def test_preorder_date_is_written_before_enabling_oversell(self):
        v = variant()
        sh = FakeShopify([v])
        d = decide({'idTypeDispo': 2, 'dateArrivage': '2099-12-16'}, 0)
        sync.apply_variant(sh, v, d)
        self.assertEqual(sh.calls, [('date', 'vA', '2099-12-16'), ('policy', 'vA', 'CONTINUE')])

    def test_stopped_disables_oversell_before_clearing_date(self):
        v = variant(policy='CONTINUE', arrival='2099-12-16')
        sh = FakeShopify([v])
        sync.apply_variant(sh, v, decide({'availabilityLabel': 'Product stopped'}, 0))
        self.assertEqual(sh.calls, [('policy', 'vA', 'DENY'), ('date', 'vA', None)])

    def test_second_run_makes_no_writes(self):
        v = variant()
        sh = FakeShopify([v])
        d = decide({'idTypeDispo': 2, 'dateArrivage': '2099-12-16'}, 0)
        sync.apply_variant(sh, v, d)
        sh.calls.clear()
        sync.apply_variant(sh, v, d)
        self.assertEqual(sh.calls, [])

    def test_api_user_errors_fail_the_job_instead_of_reporting_success(self):
        sh = object.__new__(sync.Shopify)
        sh.gql = lambda q, v: {'metafieldsSet': {'userErrors': [{'message': 'Denied'}]}}
        with self.assertRaises(RuntimeError):
            sh.set_metafield_date('vA', '2099-12-16')

    def test_duplicate_job_launch_is_rejected_until_finished(self):
        store = JobStore()
        first = store.create_if_idle('sync.py')
        self.assertIsNone(store.create_if_idle('sync.py'))
        store.mutate(first.id, status='success')
        self.assertIsNotNone(store.create_if_idle('sync.py'))

    def test_dry_run_writes_report_but_no_shopify_mutations_or_quantities(self):
        v = variant(quantity=7, policy='CONTINUE', arrival='2099-12-16')
        sh = FakeShopify([v])
        supplier = type('Supplier', (), {'login': lambda self: None,
                   'fetch_all_products': lambda self: {'A': {'availabilityLabel': 'Product stopped'}}})()
        with tempfile.TemporaryDirectory() as tmp, patch.object(sync, 'DRY_RUN', True), \
             patch.object(sync, 'REPORT_FILE', str(Path(tmp) / 'report.csv')), \
             patch.object(sync.runtime, 'require_env'), patch.object(sync, 'EasyRea', return_value=supplier), \
             patch.object(sync, 'Shopify', return_value=sh):
            sync.main()
            with Path(sync.REPORT_FILE).open(encoding='utf-8-sig') as report:
                row = list(csv.DictReader(report))[0]
            self.assertEqual(row['target_policy'], 'DENY')
            self.assertEqual(row['quantity_preserved'], '7')
        self.assertEqual(sh.calls, [])
        self.assertEqual(v['quantity'], 7)

    def test_real_run_preserves_local_qty_and_clears_product_and_variant_dates(self):
        v = variant(quantity=7, policy='CONTINUE', arrival='2099-12-16')
        sh = FakeShopify([v])
        supplier = type('Supplier', (), {'login': lambda self: None,
                   'fetch_all_products': lambda self: {'A': {'availabilityLabel': 'Product stopped'}}})()
        with tempfile.TemporaryDirectory() as tmp, patch.object(sync, 'DRY_RUN', False), \
             patch.object(sync, 'REPORT_FILE', str(Path(tmp) / 'report.csv')), \
             patch.object(sync.runtime, 'require_env'), patch.object(sync, 'EasyRea', return_value=supplier), \
             patch.object(sync, 'Shopify', return_value=sh):
            sync.main()
        self.assertEqual(v['quantity'], 7)
        self.assertEqual(v['inventory_policy'], 'DENY')
        self.assertIsNone(v['variant_date'])
        self.assertIsNone(v['product_date'])
        self.assertEqual(v['template_suffix'], '')


if __name__ == '__main__':
    unittest.main()
