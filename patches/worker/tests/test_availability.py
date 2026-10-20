from xml.etree import ElementTree as ET
import pytest
from feeds.availability import feed_availability
from feeds.availability_refresh import apply_source
from feeds.xml_export import generate, GOOGLE_NS
from feeds.favi_xml import generate_favi
from feeds.markets_normalize import normalize_market
from test_xml_audit import good_row
from test_favi_xml import BASE
from test_market_feed_rows import sample_product


@pytest.mark.parametrize("quantity", [0, -3, 2])
def test_continue_is_sellable_without_inventing_a_backorder(quantity):
    row = apply_source(good_row(), {
        "inventoryQuantity": quantity, "inventoryPolicy": "CONTINUE",
        "expectedArrival": None, "product": {"variantsCount": {"count": 1}}})
    assert row["available"] is (quantity > 0)
    assert row["availability"] == "in_stock"
    assert row["availability_date"] is None
    xml = generate([row], "BG", "google")
    assert len(ET.fromstring(xml).findall("./channel/item")) == 1
    assert ET.fromstring(xml).findtext("./channel/item/{" + GOOGLE_NS + "}availability") == "in_stock"


def test_genuine_replenishment_date_is_preserved():
    row = apply_source(good_row(), {
        "inventoryQuantity": 0, "inventoryPolicy": "CONTINUE",
        "expectedArrival": {"value": "2026-12-16"}, "product": {}})
    assert row["availability"] == "backorder"
    assert row["availability_date"] == "2026-12-16T00:00:00+02:00"
    xml = generate([row], "BG", "google")
    assert b"2026-12-16T00:00:00+02:00" in xml
    assert len(ET.fromstring(xml).findall("./channel/item")) == 1


def test_one_colour_cannot_borrow_another_colours_product_date():
    source = {"inventoryQuantity": 0, "inventoryPolicy": "CONTINUE",
              "expectedArrival": None,
              "product": {"variantsCount": {"count": 2},
                          "expectedArrival": {"value": "2026-12-16"}}}
    assert apply_source(good_row(), source)["availability_date"] is None
    source["product"]["variantsCount"]["count"] = 1
    assert apply_source(good_row(), source)["availability_date"] == "2026-12-16T00:00:00+02:00"


def test_zero_stock_deny_is_not_sellable():
    row = apply_source(good_row(), {"inventoryQuantity": 0,
                                   "inventoryPolicy": "DENY", "product": {}})
    assert row["availability"] == "out_of_stock"
    assert len(ET.fromstring(generate([row], "BG", "google")).findall("./channel/item")) == 0


def test_favi_keeps_continue_without_backorder_date():
    row = {**BASE, "available": False, "continue_selling": True}
    xml, report = generate_favi([row], "BG")
    assert report["items_exported"] == 1
    assert report["excluded_reasons"] == {}
    assert b"in_stock" in xml


def test_normalizer_reads_arrival_and_retains_physical_stock():
    product = sample_product()
    variant = product["variants"]["nodes"][0]
    variant.update(inventoryQuantity=0, inventoryPolicy="CONTINUE")
    row = normalize_market(product, "RO")[0]
    assert row["availability"] == "in_stock" and not row["available"]
    variant["expectedArrival"] = {"value": "2026-12-16"}
    assert normalize_market(product, "RO")[0]["availability"] == "backorder"
