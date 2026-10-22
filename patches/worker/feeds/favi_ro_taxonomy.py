"""Conservative Shopify taxonomy to observed FAVI Romania category paths.

Only exact source leaves with a matching live FAVI.ro category are included.
The remaining products are reported as unmapped, never assigned a broad guess.
"""

TAXONOMY_TO_FAVI_RO = {
    "gid://shopify/TaxonomyCategory/hg-11-2-3-13-1": "bucătărie > accesorii pentru gătit > tigăi",
    "gid://shopify/TaxonomyCategory/hg-10-16-6": "Cutii și coșuri pentru depozitare",
    "gid://shopify/TaxonomyCategory/hg-10-9-16": "echipament pentru baie > accesorii pentru baie > coșuri de rufe",
    "gid://shopify/TaxonomyCategory/fr-19-1-4": "mobilă > spațiu de depozitare > etajere",
    "gid://shopify/TaxonomyCategory/hg-3-47": "decorațiuni > oglinzi",
    "gid://shopify/TaxonomyCategory/hg-3-57": "textile de uz casnic > covoare",
    "gid://shopify/TaxonomyCategory/hg-3-67": "decorațiuni > vaze",
    "gid://shopify/TaxonomyCategory/hg-13-5-1": "corpuri de iluminat > lămpi de masă",
    "gid://shopify/TaxonomyCategory/hg-13-5-3": "corpuri de iluminat > lămpi de podea",
    "gid://shopify/TaxonomyCategory/hg-13-9-5": "corpuri de iluminat > lustre",
    "gid://shopify/TaxonomyCategory/hg-3-74-1-1": "textile de uz casnic > perdele",
    "gid://shopify/TaxonomyCategory/hg-3-64": "textile de uz casnic > perne și fețe de perne",
    "gid://shopify/TaxonomyCategory/hg-11-8-21": "bucătărie > accesorii pentru gătit > tocătoare de bucătărie",
    "gid://shopify/TaxonomyCategory/hg-11-10-7-9": "bucătărie > servirea mesei > platouri și tăvi",
    "gid://shopify/TaxonomyCategory/hg-1-2": "echipament pentru baie > textile pentru baie > covorașe de baie",
    "gid://shopify/TaxonomyCategory/hg-1-15": "echipament pentru baie > accesorii pentru baie > dozatoare de săpun",
    "gid://shopify/TaxonomyCategory/hg-15-1-2": "dormitor > textile pentru dormitor > cearșafuri",
    "gid://shopify/TaxonomyCategory/hg-11-2-1-5": "bucătărie > accesorii coacere > forme pentru copt",
    "gid://shopify/TaxonomyCategory/hg-11-2-1-6": "bucătărie > accesorii coacere > forme pentru copt",
    "gid://shopify/TaxonomyCategory/hg-11-2-1-3": "bucătărie > accesorii coacere > forme pentru copt",
    "gid://shopify/TaxonomyCategory/hg-11-2-1-8": "bucătărie > accesorii coacere > tăvi de copt",
    "gid://shopify/TaxonomyCategory/fr-15-6-5": "grădină > mese de grădină",
    "gid://shopify/TaxonomyCategory/fr-15-6-12": "grădină > mese de grădină",
    "gid://shopify/TaxonomyCategory/fr-15-6-3": "grădină > mese de grădină",
    "gid://shopify/TaxonomyCategory/fr-15-4-2": "grădină > scaune de grădină",
    "gid://shopify/TaxonomyCategory/fr-15-4-5": "grădină > șezlonguri de grădină și terasă",
    "gid://shopify/TaxonomyCategory/fr-24-1-1": "mobilă > mese și măsuțe > măsuțe de cafea",
    "gid://shopify/TaxonomyCategory/fr-24-6": "mobilă > mese și măsuțe > noptiere",
    "gid://shopify/TaxonomyCategory/fr-4-5": "mobilă > dulapuri și comode > comode",
    "gid://shopify/TaxonomyCategory/fr-4-14-1-1": "mobilă > dulapuri și comode > dulapuri de baie",
    "gid://shopify/TaxonomyCategory/fr-7-1-1": "mobilă > mobilier de șezut > fotolii",
    "gid://shopify/TaxonomyCategory/hg-3-40-2": "decorațiuni > sfeșnice și lumânări > lumânări",
    "gid://shopify/TaxonomyCategory/hg-3-4-2-3": "decorațiuni > tablouri",
    "gid://shopify/TaxonomyCategory/hg-3-17-4": "decorațiuni > ceasuri",
    "gid://shopify/TaxonomyCategory/hg-3-52": "decorațiuni > rame foto",
    "gid://shopify/TaxonomyCategory/hg-10-18-4-1": "bucătărie > organizare și curățenie > coșuri de gunoi",
}


def categories_for_products(products, explicit=None):
    result = {}
    for product in products:
        taxonomy = (product.get("category") or {}).get("id")
        path = TAXONOMY_TO_FAVI_RO.get(taxonomy)
        if path:
            result[product["id"]] = {"market": "RO", "verified": True, "path": path}
    result.update(explicit or {})
    return result
