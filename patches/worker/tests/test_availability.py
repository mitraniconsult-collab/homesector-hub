from xml.etree import ElementTree as ET
import pytest
from feeds.availability import feed_availability
from feeds.availability_refresh import apply_source
from feeds import availability_refresh
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


def test_http_200_graphql_throttle_resumes_same_batch(monkeypatch):
    responses = iter([
        {"errors": [{"extensions": {"code": "THROTTLED"}}],
         "extensions": {"cost": {"requestedQueryCost": 100,
                                  "throttleStatus": {"currentlyAvailable": 0, "restoreRate": 50}}}},
        {"data": {"nodes": [{"id": "v1"}]}}])
    calls, delays = [], []
    def post(endpoint, token, payload):
        calls.append(payload["variables"]["ids"])
        return next(responses)
    monkeypatch.setattr(availability_refresh, "shopify_post", post)
    monkeypatch.setattr(availability_refresh.time, "sleep", delays.append)
    assert availability_refresh.read_nodes("endpoint", "token", ["v1"]) == [{"id": "v1"}]
    assert calls == [["v1"], ["v1"]] and delays == [2.25]


def test_refresh_replaces_stale_price_and_retains_variant_name():
    row = availability_refresh.apply_current_offer(
        {**good_row(), "price": "739", "title": "Table"},
        {"displayName": "Table - Copper", "price_BG": {
            "price": {"amount": "690.0", "currencyCode": "EUR"}}})
    assert row["price"] == "690.0" and row["title"] == "Table - Copper"
    assert b"Table - Copper" in generate([row], "BG", "google")


@pytest.mark.parametrize("amount,currency", [("NaN", "EUR"), ("0", "EUR"), ("10", "BGN"), (None, "EUR")])
def test_refresh_rejects_invalid_current_price(amount, currency):
    with pytest.raises(RuntimeError):
        availability_refresh.apply_current_offer(good_row(), {
            "displayName": "Table", "price_BG": {"price": {
                "amount": amount, "currencyCode": currency}}})


def test_bg_catalog_preserves_variant_name():
    product = sample_product()
    product["published_BG"] = True
    variant = product["variants"]["nodes"][0]
    variant.update(displayName="Тиган - Червен", price_BG={"price": {"amount": "10", "currencyCode": "EUR"}})
    assert normalize_market(product, "BG")[0]["title"] == "Тиган - Червен"


def test_last_read_updates_description_and_drops_unpublished_product():
    source = {"inventoryQuantity": 0, "inventoryPolicy": "CONTINUE",
              "product": {"status": "ACTIVE", "published_BG": False,
                          "descriptionHtml": "<p>Актуално описание</p>"}}
    row = apply_source(good_row(), source)
    assert row["description"] == "Актуално описание"
    assert row["continue_selling"] and row["availability"] == "in_stock"
    assert not ET.fromstring(generate([row], "BG", "google")).findall("./channel/item")
