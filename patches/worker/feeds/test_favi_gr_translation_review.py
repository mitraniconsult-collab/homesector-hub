import unittest

from feeds.favi_gr_translation_review import review_row


class GreekTranslationReviewTests(unittest.TestCase):
    def setUp(self):
        self.product = {"id": "gid://shopify/Product/123", "handle": "storage-box"}
        self.category = {"path": "Κουτιά αποθήκευσης"}
        self.resource = {
            "resourceId": self.product["id"],
            "translatableContent": [
                {"key": "title", "value": "Кутия", "digest": "title-hash"},
                {"key": "body_html", "value": "<p>Описание</p>", "digest": "body-hash"},
            ],
            "translations": [
                {"key": "title", "value": "Κουτί", "outdated": False},
            ],
        }

    def test_missing_body_stays_pending_and_preserves_existing_title(self):
        row = review_row(self.product, self.category, self.resource)
        self.assertEqual(row["greek_title"], "Κουτί")
        self.assertEqual(row["reviewed_greek_title"], "")
        self.assertEqual(row["body_html_digest"], "body-hash")
        self.assertFalse(row["title_needs_review"])
        self.assertTrue(row["body_html_needs_review"])

    def test_complete_non_outdated_copy_is_not_exported(self):
        self.resource["translations"].append(
            {"key": "body_html", "value": "<p>Περιγραφή</p>", "outdated": False})
        self.assertIsNone(review_row(self.product, self.category, self.resource))

    def test_outdated_translation_is_exported(self):
        self.resource["translations"][0]["outdated"] = True
        row = review_row(self.product, self.category, self.resource)
        self.assertTrue(row["title_needs_review"])

    def test_requires_source_digest(self):
        self.resource["translatableContent"][0]["digest"] = None
        with self.assertRaises(RuntimeError):
            review_row(self.product, self.category, self.resource)


if __name__ == "__main__":
    unittest.main()
