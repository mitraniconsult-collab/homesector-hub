"""Apply existing verified Shopify translations; never invent translated product content."""
from .markets_normalize import plain_text
from .config import MARKETS

KEYS = {"title", "body_html", "handle"}

def apply_verified_translations(row, translations, market, url_verified=False):
    if market not in MARKETS:
        raise ValueError("Unsupported market")
    new_row = dict(row)
    if market == "BG":
        new_row["verified_locale"] = "bg"
        new_row["verified_market_url"] = True
        return new_row
    localized = {
        item.get("key"): item.get("value")
        for item in (translations or [])
        if item and item.get("key") in KEYS and item.get("value")
    }
    if localized.get("title"):
        new_row["title"] = localized["title"].strip()
    if localized.get("body_html"):
        new_row["description"] = plain_text(localized["body_html"])
    # Both title and description must exist as translations.
    if localized.get("title") and localized.get("body_html"):
        new_row["verified_locale"] = MARKETS[market]["language"]
    # Do not assume that a Shopify handle translation is available or that
    # the market domain resolves to this product without verification.
    new_row["verified_market_url"] = bool(url_verified)
    return new_row


# Common source color words catch obvious wrong option translations. The
# Shopify variant (not another variant's label) is the sole source of color.
_GR_BASIC_COLORS = {
    "кафяв": "καφέ", "бежов": "μπεζ", "бял": "λευκό",
    "черен": "μαύρο", "син": "μπλε", "зелен": "πράσινο",
}
_RO_BASIC_COLORS = {
    "кафяв": "maro", "бежов": "bej", "бял": "alb",
    "черен": "negru", "син": "albastru", "зелен": "verde",
}
_HU_BASIC_COLORS = {
    "кафяв": "barna", "бежов": "bézs", "бял": "fehér",
    "черен": "fekete", "син": "kék", "зелен": "zöld",
}


def _has_cyrillic(value):
    return any("\u0400" <= character <= "\u04ff" for character in value)

def localize_variant_color(row, variant_translations, market):
    output = dict(row)
    option_index = row.get("color_option_index")
    if not option_index:
        output["verified_variant_color"] = True
        return output
    if market == "BG":
        output["verified_variant_color"] = True
        return output
    values = {entry.get("key"): str(entry.get("value") or "").strip()
              for entry in (variant_translations or [])
              if entry and entry.get("outdated") is not True}
    value = values.get("option" + str(option_index), "")
    # Never send the Bulgarian source label to an international FAVI catalog.
    output["color"] = None
    source = str(row.get("color") or "").casefold().strip()
    expected = {"GR": _GR_BASIC_COLORS, "RO": _RO_BASIC_COLORS,
                "HU": _HU_BASIC_COLORS}.get(market, {}).get(source)
    if market == "GR" and value and any("\u0370" <= c <= "\u03ff" for c in value) \
            and (not expected or value.casefold() == expected):
        output["color"] = value
        output["verified_variant_color"] = True
    elif market in ("RO", "HU") and value and not _has_cyrillic(value) \
            and (not expected or value.casefold() == expected) \
            and (value.casefold() != source or not _has_cyrillic(source)):
        output["color"] = value
        output["verified_variant_color"] = True
    else:
        output["verified_variant_color"] = False
    return output


# The option name comes from Shopify's source catalog; only the option value
# may come from Shopify's actual Greek variant translations. Unknown options
# remain untouched instead of creating an unverified Greek label.
_GR_VARIANT_OPTION_LABELS = {
    "аромат": "Άρωμα", "fragrance": "Άρωμα", "scent": "Άρωμα",
    "размер": "Μέγεθος", "size": "Μέγεθος",
    "материал": "Υλικό", "material": "Υλικό",
    "дизайн": "Σχέδιο", "design": "Σχέδιο",
    "финиш": "Φινίρισμα", "finish": "Φινίρισμα",
    "стъкло": "Γυαλί", "glass": "Γυαλί",
    "капацитет": "Χωρητικότητα", "capacity": "Χωρητικότητα",
}
_GR_COLOR_OPTIONS = {"color", "colour", "цвят", "цвет"}
_RO_VARIANT_OPTION_LABELS = {
    "аромат": "Aromă", "fragrance": "Aromă", "scent": "Aromă",
    "размер": "Mărime", "size": "Mărime",
    "материал": "Material", "material": "Material",
    "дизайн": "Design", "design": "Design",
    "финиш": "Finisaj", "finish": "Finisaj",
    "стъкло": "Sticlă", "glass": "Sticlă",
    "капацитет": "Capacitate", "capacity": "Capacitate",
}
_HU_VARIANT_OPTION_LABELS = {
    "аромат": "Illat", "fragrance": "Illat", "scent": "Illat",
    "размер": "Méret", "size": "Méret",
    "материал": "Anyag", "material": "Anyag",
    "дизайн": "Minta", "design": "Minta",
    "финиш": "Felület", "finish": "Felület",
    "стъкло": "Üveg", "glass": "Üveg",
    "капацитет": "Űrtartalom", "capacity": "Űrtartalom",
}


def localize_variant_details(row, variant_translations, market):
    """Describe a variant using only its current market Shopify option values."""
    output = dict(row)
    if market not in ("GR", "RO", "HU") or output.get("verified_locale") != \
            {"GR": "el", "RO": "ro", "HU": "hu"}[market]:
        return output
    values = {entry.get("key"): str(entry.get("value") or "").strip()
              for entry in (variant_translations or [])
              if entry and entry.get("outdated") is not True}
    details = []
    for index, option in enumerate(row.get("variant_options") or [], start=1):
        source_name = str(option.get("name") or "").strip().casefold()
        if source_name in _GR_COLOR_OPTIONS:
            continue
        label = {"GR": _GR_VARIANT_OPTION_LABELS, "RO": _RO_VARIANT_OPTION_LABELS,
                 "HU": _HU_VARIANT_OPTION_LABELS}[market].get(source_name)
        source_value = str(option.get("value") or "").strip()
        value = values.get("option" + str(index), "")
        if not label or not source_value or not value:
            continue
        # Greek text is required for descriptive choices. Numeric dimensions
        # are language neutral, but still require an explicit Greek translation.
        if market == "GR":
            greek = any("\u0370" <= character <= "\u03ff" for character in value)
            if not greek and not (label == "Μέγεθος" and
                                  all(c.isdigit() or c in ".,xX× /-cmCM" for c in value)):
                continue
        elif _has_cyrillic(value) or (value.casefold() == source_value.casefold()
                                     and _has_cyrillic(source_value)):
            continue
        details.append(f"{label}: {value}")
    if details:
        suffix = " · ".join(details)
        output["title"] = str(output.get("title") or "").rstrip() + " — " + suffix
        output["description"] = (str(output.get("description") or "").rstrip() +
                                 " " + suffix + ".").strip()
    return output
