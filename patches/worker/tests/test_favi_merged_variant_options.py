"""Merged Shopify products keep their translated variant choices in FAVI."""
from feeds.localization import localize_variant_details


def test_merged_variant_choice_uses_only_current_market_translation():
    row = {
        "title": "Localized table", "description": "Localized description",
        "variant_options": [{"name": "Вариант", "value": "Кехлибарено стъкло"}],
    }
    cases = (
        ("GR", "el", "Κεχριμπαρένιο γυαλί", "Παραλλαγή"),
        ("RO", "ro", "Sticlă ambră", "Variantă"),
        ("HU", "hu", "Borostyánszínű üveg", "Változat"),
    )
    for market, locale, value, label in cases:
        source = {**row, "verified_locale": locale}
        translated = [{"key": "option1", "value": value, "outdated": False}]
        result = localize_variant_details(source, translated, market)
        assert result["title"] == f"Localized table — {label}: {value}"
        assert f"{label}: {value}" in result["description"]
        assert localize_variant_details(source, [], market)["title"] == row["title"]
        assert localize_variant_details(
            source, [{**translated[0], "outdated": True}], market
        )["title"] == row["title"]
