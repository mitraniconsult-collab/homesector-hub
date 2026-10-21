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
    "gid://shopify/TaxonomyCategory/hg-10-16-1-4": (
        "Κρεμάστρες ρούχων", "https://favi.gr/proionta/kathgoria/kremastres-rouhwn"),
    "gid://shopify/TaxonomyCategory/hg-10-16-10": (
        "Κουτιά αποθήκευσης και οργάνωσης > Καλάθια αποθήκευσης",
        "https://favi.gr/proionta/kathgoria/koutia-apothikeusis-kai-organwsis/kalathia-apothikefsis"),
    "gid://shopify/TaxonomyCategory/fr-4-5": (
        "Συρταριέρες", "https://favi.gr/proionta/kathgoria/syrtarieres"),
    "gid://shopify/TaxonomyCategory/fr-24-1-1": (
        "Τραπεζάκια σαλονιού", "https://favi.gr/proionta/kathgoria/trapezakia-saloniou"),
    "gid://shopify/TaxonomyCategory/fr-24-4": (
        "Τραπέζια τραπεζαρίας", "https://favi.gr/proionta/kathgoria/trapezia-trapezarias"),
    "gid://shopify/TaxonomyCategory/fr-24-6": (
        "Κομοδίνα υπνοδωματίου", "https://favi.gr/proionta/kathgoria/komodina-upnodwmatiou"),
    "gid://shopify/TaxonomyCategory/hg-1-2": (
        "Χαλάκια μπάνιου", "https://favi.gr/proionta/kathgoria/halakia-mpaniou"),
    "gid://shopify/TaxonomyCategory/hg-10-9-4-2": (
        "Απλώστρες", "https://favi.gr/proionta/kathgoria/aplwstres"),
    "gid://shopify/TaxonomyCategory/hg-3-40-2": (
        "Κεριά", "https://favi.gr/proionta/kathgoria/keria"),
    "gid://shopify/TaxonomyCategory/hg-11-10-7-8": (
        "Πιάτα σερβιρίσματος", "https://favi.gr/proionta/kathgoria/piata-servirismatos"),
    "gid://shopify/TaxonomyCategory/fr-15-6-12": (
        "Κήπος > Τραπέζια κήπου", "https://favi.gr/proionta/kathgoria/trapezia-kipou"),
    "gid://shopify/TaxonomyCategory/fr-15-6-3": (
        "Κήπος > Τραπέζια κήπου", "https://favi.gr/proionta/kathgoria/trapezia-kipou"),
}

# Confirmed source category errors. Exclude only these product IDs from the
# automatic Food Storage Containers mapping; an explicit reviewed override can
# still assign the correct FAVI category later.
AUTO_CATEGORY_EXCLUSIONS = {
    "gid://shopify/Product/10980173709579": "gid://shopify/TaxonomyCategory/hg-11-4-6",  # Jarro jar tongs
    "gid://shopify/Product/8730408747275": "gid://shopify/TaxonomyCategory/hg-11-4-6",  # Klausberg coffee grinder
}


def categories_for_products(products, explicit):
    result = {}
    for product in products:
        taxonomy = (product.get("category") or {}).get("id")
        if AUTO_CATEGORY_EXCLUSIONS.get(product["id"]) == taxonomy:
            continue
        match = TAXONOMY_TO_FAVI_GR.get(taxonomy)
        if match:
            result[product["id"]] = {"market": "GR", "verified": True, "path": match[0]}
    result.update(explicit)
    return result

