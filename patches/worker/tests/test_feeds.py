"""Unit tests for market filtering and XML serialization."""
import unittest
from xml.etree import ElementTree as ET
from feeds.xml_export import generate

PRODUCT = {
    "id": "test-sku", "title": "Test chair", "description": "Chair",
    "link": "https://homesector.bg/products/chair",
    "image_link": "https://homesector.bg/files/chair.jpg",
    "price": "49.00", "currency": "EUR", "active": True,
    "published": True, "available": True, "markets": ["BG"],
}


class FeedTests(unittest.TestCase):
    def test_google_xml(self):
        xml = generate([PRODUCT], "BG", "google")
        self.assertEqual(len(ET.fromstring(xml).findall("./channel/item")), 1)
        self.assertIn(b"49.00 EUR", xml)

    def test_market_filter(self):
        self.assertEqual(len(ET.fromstring(generate([PRODUCT], "GR", "meta")).findall("./channel/item")), 0)

    def test_missing_image(self):
        product = dict(PRODUCT, image_link="")
        self.assertEqual(len(ET.fromstring(generate([product], "BG", "google")).findall("./channel/item")), 0)

    def test_unsupported_market(self):
        with self.assertRaises(ValueError):
            generate([PRODUCT], "US", "google")


if __name__ == "__main__":
    unittest.main()
