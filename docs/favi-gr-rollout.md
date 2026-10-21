# FAVI Greece rollout status (2026-10-21)

## Live partial preview

- XML: https://hub.homesector.bg/feeds/favi/GR-preview.xml
- Diagnostics: https://hub.homesector.bg/feeds/favi/GR-preview-report.json
- Verified public HTTP 200; 185 RSS items, 185 distinct variant IDs, 101 Shopify
  parent group IDs. All 185 prices are EUR; 65 XML links use verified Greek
  collection-context paths. SHA-256: 761b9501933b3f87b13dbd1977e6e21e26d3d4d58d0ee1bbffd0c7b1c327ca73.
- The preview is labeled partial_preview and noindex. No FAVI destination
  subscription was changed; approved_by_favi remains false.

The worker scanned 19,303 Shopify products; 8,444 are active and published in
GR. Seven reviewed Shopify taxonomy mappings cover 755 products. Direct Greek
landing pages verified for 147; an additional 145 product pages verified through
actual Shopify collection memberships. The URL preflight thus has 292 verified
products, of which 101 parent products produced eligible XML items after
translation, variant color, sellability and content checks.

The direct URL verifier now decodes percent-encoded Cyrillic handles before
comparison. Collection links are accepted only if Shopify lists the product in
the collection, the final response is a 200 HTML page on homesector.gr with the
same path and handle, and the market row uses that individually verified URL.
Collection checks are bounded to two specific collection paths and a five-second
network timeout. Shopify lookup uses four memberships per product to control
query cost. The public pointer changes only after XML audit, unique-ID check,
immutable Blob upload and hash verification.

Color variants keep separate variant IDs and share g:item_group_id for the
Shopify parent. Zero-quantity CONTINUE remains eligible. Greek copy and colors
are sourced from Shopify; Cleon's reversed color translations stay excluded.

## Remaining gates

1. Expand reviewed FAVI Greece category mappings across the catalog. Seven
   mapped taxonomies cover only 755 of 8,444 GR active and published products;
   many products have no usable Shopify taxonomy at all.
2. Resolve Greek storefront address coverage and localization. 463 of the
   755 mapped products did not yield a verified GR page in this run. The
   storefront also shows Bulgarian navigation labels on sampled Greek pages.
3. Correct missing or reversed Greek product/variant translations. The
   preflight report has overlapping variant-level exclusion reasons; do not
   sum them as distinct products. Source-specific checks are needed before
   including blocked rows.
4. Replace the completed source journal with recurring fresh catalog
   generations and an age/decline guard before pointer changes. The current
   19,303-product source is a snapshot; a worker restart recalculates the
   preview from the same source, not newly created Shopify products.
5. Verify the separate FAVI Greece registration, submit a complete reviewed
   feed, inspect their import feedback, and then switch the destination
   subscription. Petya's 2026-09-25 email mentioned a separate country
   registration and a Greek trial; acceptance remains unverified.

The published URL is for human review, not the completed FAVI Greece catalog.
