"""Reviewed Shopify taxonomy to FAVI Greece paths.

Each leaf was checked against the named live FAVI category; unrelated taxonomy
IDs remain unmapped. FAVI can adjust its own category match at onboarding.
"""
TAXONOMY_TO_FAVI_GR = {
    "gid://shopify/TaxonomyCategory/hg-10-16-6": (
        "Κουτιά αποθήκευσης και οργάνωσης > Κουτιά αποθήκευσης",
        "https://favi.gr/proionta/kathgoria/koutia-apothikeusis-kai-organwsis/koutia-apothikefsis"),
    "gid://shopify/TaxonomyCategory/hg-11-4-6": (
        "Αποθήκευση τροφίμων > Δοχεία τροφίμων",
        "https://favi.gr/proionta/kathgoria/doheia-trofimwn"),
    "gid://shopify/TaxonomyCategory/fr-15-6-5": (
        "Κήπος > Τραπέζια κήπου",
        "https://favi.gr/proionta/kathgoria/trapezia-kipou"),
    "gid://shopify/TaxonomyCategory/hg-10-9-16": (
        "Καλάθια απλύτων",
        "https://favi.gr/proionta/kathgoria/kalathia-aplutwn"),
    "gid://shopify/TaxonomyCategory/hg-11-10-7-9": (
        "Δίσκοι σερβιρίσματος",
        "https://favi.gr/proionta/kathgoria/diskoi-servirismatos"),
    "gid://shopify/TaxonomyCategory/hg-11-8-21": (
        "Επιφάνειες κοπής",
        "https://favi.gr/proionta/kathgoria/epifaneies-kopis"),
    "gid://shopify/TaxonomyCategory/hg-3-64": (
        "Διακοσμητικά μαξιλάρια και μαξιλαροθήκες > Διακοσμητικά μαξιλάρια",
        "https://favi.gr/proionta/kathgoria/maxilarakia-richtaria-kai-maxilarothikes/diakosmitika-maxilaria"),
    "gid://shopify/TaxonomyCategory/hg-3-47": (
        "Καθρέφτες", "https://favi.gr/proionta/kathgoria/kathreftes"),
    "gid://shopify/TaxonomyCategory/hg-3-57": (
        "Χαλιά", "https://favi.gr/proionta/kathgoria/halia"),
    "gid://shopify/TaxonomyCategory/hg-11-2-3-13-1": (
        "Τηγάνια", "https://favi.gr/proionta/kathgoria/tigania"),
    "gid://shopify/TaxonomyCategory/hg-15-1-2": (
        "Σεντόνια", "https://favi.gr/proionta/kathgoria/sentonia"),
    "gid://shopify/TaxonomyCategory/hg-12-2-8-1": (
        "Ομπρέλες κήπου", "https://favi.gr/proionta/kathgoria/ompreles-kipou"),
    "gid://shopify/TaxonomyCategory/hg-10-18-4-1": (
        "Κάδοι απορριμμάτων", "https://favi.gr/proionta/kathgoria/kadoi-aporrimmatwn"),
}


def categories_for_products(products, explicit):
    result = {}
    for product in products:
        taxonomy = (product.get("category") or {}).get("id")
        match = TAXONOMY_TO_FAVI_GR.get(taxonomy)
        if match:
            result[product["id"]] = {"market": "GR", "verified": True, "path": match[0]}
    result.update(explicit)
    return result

