import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "easyrea"))
from ean_barcodes import ean, classification


class EanBatchTests(unittest.TestCase):
    def test_ean_13_and_8(self):
        self.assertTrue(ean("8433774741985"))
        self.assertTrue(ean("96385074"))
        self.assertFalse(ean("8433774741984"))
        self.assertFalse(ean("96385075"))

    def test_reject_other_identifiers(self):
        for value in ["", "123", "123456789012", "12345678901234", "ABC12345678", "１２３４５６７８", None]:
            self.assertFalse(ean(value))

    def test_classification(self):
        make=lambda nodes, more=False: {"barcodes":{"nodes":nodes,"pageInfo":{"hasNextPage":more}}}
        good={"value":"8433774741985","type":None}
        self.assertEqual(classification(make([])), "NO_BARCODE")
        self.assertEqual(classification(make([good])), "UPDATE")
        self.assertEqual(classification(make([{"value":good["value"],"type":"EAN"}])), "ALREADY_EAN")
        self.assertEqual(classification(make([{"value":"8433774741984","type":None}])), "REVIEW_NON_EAN")
        self.assertEqual(classification(make([good],True)), "REVIEW_TRUNCATED")
        self.assertEqual(classification(make([good,{"value":"not-an-ean","type":"GTIN"}])), "REVIEW_NON_EAN")


if __name__=="__main__":
    unittest.main()
