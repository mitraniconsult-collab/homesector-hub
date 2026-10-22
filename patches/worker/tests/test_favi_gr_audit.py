import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feeds.favi_gr_audit import audit_favi_gr


def item(item_id, link, category="Φωτιστικά", group="parent", title="Lamp", description="Detail", color=""):
    return (f"<item><g:id>{item_id}</g:id><link>{link}</link>"
            f"<g:product_type>{category}</g:product_type>"
            f"<g:item_group_id>{group}</g:item_group_id>"
            f"<title>{title}</title><description>{description}</description>"
            f"<g:color>{color}</g:color></item>")


def rss(*items):
    return ('<rss xmlns:g="http://base.google.com/ns/1.0"><channel>'
            + "".join(items) + '</channel></rss>').encode()


class FaviGRAuditTests(unittest.TestCase):
    def test_distinct_variant_urls_and_group_pass(self):
        result = audit_favi_gr(rss(
            item("v1", "https://homesector.gr/products/lamp?variant=1", color="Μπλε"),
            item("v2", "https://homesector.gr/products/lamp?variant=2", color="Κόκκινο")))
        self.assertTrue(result["passed"])
        self.assertEqual(result["warnings"]["indistinguishable_variant_groups"], 0)

    def test_duplicate_full_url_is_blocking(self):
        result = audit_favi_gr(rss(
            item("v1", "https://homesector.gr/products/lamp?variant=1"),
            item("v2", "https://homesector.gr/products/lamp?variant=1")))
        self.assertFalse(result["passed"])
        self.assertEqual(result["issues"], {"duplicate_product_link": 1})

    def test_missing_category_or_parent_is_blocking(self):
        result = audit_favi_gr(rss(
            item("v1", "https://homesector.gr/products/lamp?variant=1", category=""),
            item("v2", "https://homesector.gr/products/lamp?variant=2", group="")))
        self.assertFalse(result["passed"])
        self.assertEqual(result["issues"],
                         {"missing_favi_category": 1, "missing_parent_group": 1})

    def test_indistinguishable_variants_are_reported(self):
        result = audit_favi_gr(rss(
            item("v1", "https://homesector.gr/products/lamp?variant=1"),
            item("v2", "https://homesector.gr/products/lamp?variant=2")))
        self.assertTrue(result["passed"])
        self.assertEqual(result["warnings"]["indistinguishable_variant_groups"], 1)
        self.assertEqual(result["warnings"]["sample_group_ids"], ["parent"])


if __name__ == "__main__":
    unittest.main()
