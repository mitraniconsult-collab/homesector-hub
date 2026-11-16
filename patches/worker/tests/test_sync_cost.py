import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "easyrea"))
from sync_cost import assess, supplier_cost


class SyncCostTests(unittest.TestCase):
    def test_supplier_cents_round_up_to_whole_euros(self):
        for cents, expected in ((643, 7), (700, 7), (701, 8), (1, 1)):
            with self.subTest(cents=cents):
                self.assertEqual(supplier_cost(cents), (Decimal(cents) / 100, Decimal(expected)))

    def test_bad_supplier_prices_do_not_overwrite_shopify(self):
        for value in (None, "", 0, -1, "NaN", "Infinity", "6.43"):
            with self.subTest(value=value):
                self.assertEqual(supplier_cost(value), (None, None))

    def test_ambiguous_or_mismatched_variants_do_not_update(self):
        variant = {
            "sku": "123A", "barcode": "123",
            "product": {"status": "ACTIVE", "vendor": "atmosphera"},
            "inventoryItem": {"unitCost": {"amount": "72.00", "currencyCode": "EUR"}},
        }
        catalog = {"123A": {"marque": "ATMOSPHERA", "gencode": "123", "prixAchat": 643}}
        self.assertEqual(assess(variant, catalog, set(), {"123A": 1}), (72, Decimal("6.43"), 7, "UPDATE"))
        self.assertEqual(assess(variant, catalog, {"123A"}, {"123A": 1})[-1], "SKU_CONFLICT")
        self.assertEqual(assess(variant, catalog, set(), {"123A": 2})[-1], "SKU_CONFLICT")
        variant["barcode"] = "456"
        self.assertEqual(assess(variant, catalog, set(), {"123A": 1})[-1], "IDENTITY_MISMATCH")
