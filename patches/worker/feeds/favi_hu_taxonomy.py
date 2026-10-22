"""Exact Shopify leaves mapped to observed FAVI.hu category paths.

Unmapped products stay out of the preview. Review the live FAVI category list
before expanding this map: https://favi.hu/partner-dashboard/category-list
"""

TAXONOMY_TO_FAVI_HU = {
    "gid://shopify/TaxonomyCategory/hg-11-2-3-13-1": "konyha > főzéshez > serpenyők",
    "gid://shopify/TaxonomyCategory/hg-10-16-6": "bútorok > tárolás > dobozok és rendszerezők",
    "gid://shopify/TaxonomyCategory/fr-19-1-4": "bútorok > tárolás > polcrendszerek",
    "gid://shopify/TaxonomyCategory/hg-3-47": "dekoráció > tükrök",
    "gid://shopify/TaxonomyCategory/hg-3-57": "lakástextil > szőnyegek",
    "gid://shopify/TaxonomyCategory/hg-3-67": "dekoráció > vázák",
    "gid://shopify/TaxonomyCategory/hg-13-5-1": "világítás > asztali lámpák",
    "gid://shopify/TaxonomyCategory/hg-13-5-3": "világítás > állólámpák",
    "gid://shopify/TaxonomyCategory/hg-13-9-5": "világítás > függőlámpák",
    "gid://shopify/TaxonomyCategory/hg-3-74-1-1": "lakástextil > függönyök",
    "gid://shopify/TaxonomyCategory/hg-3-64": "lakástextil > díszpárnák és párnahuzatok",
    "gid://shopify/TaxonomyCategory/hg-11-8-21": "konyha > főzéshez > vágódeszkák",
    "gid://shopify/TaxonomyCategory/hg-11-10-7-9": "konyha > étkezés > tálcák",
    "gid://shopify/TaxonomyCategory/hg-1-2": "lakástextil > fürdőszobai textilek > fürdőszobai szőnyegek",
    "gid://shopify/TaxonomyCategory/hg-11-2-1-5": "konyha > sütés > sütőformák",
    "gid://shopify/TaxonomyCategory/hg-11-2-1-6": "konyha > sütés > sütőformák",
    "gid://shopify/TaxonomyCategory/hg-11-2-1-3": "konyha > sütés > sütőformák",
    "gid://shopify/TaxonomyCategory/hg-11-2-1-8": "konyha > sütés > tepsik",
    "gid://shopify/TaxonomyCategory/fr-15-6-5": "bútorok > kerti bútorok > kerti asztalok",
    "gid://shopify/TaxonomyCategory/fr-15-6-12": "bútorok > kerti bútorok > kerti asztalok",
    "gid://shopify/TaxonomyCategory/fr-15-6-3": "bútorok > kerti bútorok > kerti asztalok",
    "gid://shopify/TaxonomyCategory/fr-15-4-2": "bútorok > kerti bútorok > kerti székek és fotelek",
    "gid://shopify/TaxonomyCategory/fr-15-4-5": "bútorok > kerti bútorok > napozóágyak",
    "gid://shopify/TaxonomyCategory/fr-24-1-1": "bútorok > asztalok > dohányzóasztalok",
    "gid://shopify/TaxonomyCategory/fr-24-6": "bútorok > asztalok > éjjeliszekrények",
    "gid://shopify/TaxonomyCategory/fr-4-5": "bútorok > szekrények és komódok > komódok",
    "gid://shopify/TaxonomyCategory/fr-4-14-1-1": "bútorok > szekrények és komódok > fürdőszoba szekrények",
    "gid://shopify/TaxonomyCategory/fr-7-1-1": "nappali > fotelek",
    "gid://shopify/TaxonomyCategory/hg-3-40-2": "dekoráció > gyertyák és gyertyatartók > gyertyák",
    "gid://shopify/TaxonomyCategory/hg-3-4-2-3": "dekoráció > képek",
    "gid://shopify/TaxonomyCategory/hg-3-17-4": "dekoráció > órák",
    "gid://shopify/TaxonomyCategory/hg-3-52": "dekoráció > fényképkeretek",
    "gid://shopify/TaxonomyCategory/hg-10-18-4-1": "konyha > rendszerezés és takarítás > szemetesek",
}


def categories_for_products(products, explicit=None):
    result = {}
    for product in products:
        path = TAXONOMY_TO_FAVI_HU.get((product.get("category") or {}).get("id"))
        if path:
            result[product["id"]] = {"market": "HU", "verified": True, "path": path}
    result.update(explicit or {})
    return result
