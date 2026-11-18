import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "easyrea"))
import emag_catalog as emag


class EmagCatalogTests(unittest.TestCase):
    def test_ean_check_digit(self):
        self.assertTrue(emag.valid_ean("4006381333931"))
        self.assertTrue(emag.valid_ean("96385074"))
        self.assertFalse(emag.valid_ean("4006381333932"))
        self.assertFalse(emag.valid_ean(""))
        self.assertFalse(emag.valid_ean(" 1234 "))

    def test_variant_reports_missing_fields(self):
        item = {"id": "gid://shopify/ProductVariant/22", "sku": "", "barcode": "",
                "title": "Default Title", "price": "10", "inventoryQuantity": 0,
                "image": None, "product": {"id": "gid://shopify/Product/11",
                "title": "Test", "handle": "test", "vendor": "5five", "status": "ACTIVE",
                "descriptionHtml": "", "featuredImage": None, "category": None}}
        row = emag.convert(item, "example.myshopify.com")
        self.assertEqual(row["eligibility"], "review")
        for field in ("missing_sku", "missing_ean", "missing_image", "missing_description", "missing_shopify_category"):
            self.assertIn(field, row["issues"])
        self.assertEqual(row["inventory_shopify"], 0)

    def test_staging_has_no_emag_network_endpoint(self):
        self.assertNotIn("emag.ro/api", emag.QUERY)
        self.assertNotIn("emag.bg/api", emag.QUERY)


if __name__ == "__main__":
    unittest.main()
