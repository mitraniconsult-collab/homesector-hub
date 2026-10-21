# FAVI Greece rollout status (2026-10-21)

## Public partial preview

- XML: https://hub.homesector.bg/feeds/favi/GR-preview.xml
- Diagnostics: https://hub.homesector.bg/feeds/favi/GR-preview-report.json
- Hub dashboard: https://hub.homesector.bg/feeds
- Verified public HTTP 200: 246 XML items, 246 distinct variant IDs, 118 Shopify parent groups, and 246 EUR prices. SHA-256: aa2f164cc713c6ddf0714e4de451c65f882f8dd16950a13f36b99be7754e88b1.
- The preview is partial and noindex. No FAVI destination subscription was changed; approved_by_favi remains false.

The completed source snapshot contains 19,303 Shopify products, of which 8,444 are active and published to GR with 12,556 source variants. Sixteen reviewed Shopify taxonomy mappings cover 1,087 products. Greek title and description translations exist for 393 of these mapped products. Direct Greek URLs verified for 191 mapped products; an additional 107 collection-context product URLs verified through actual Shopify collection membership, totaling 298 distinct verified product URLs. These gates yield 246 eligible variants. Exclusion counters in the report overlap and are variant-level; do not sum them as distinct products.

The URL verifier tries the Shopify product handle and its Greek translation, requiring a 200 HTML page at the exact expected path on homesector.gr. Collection links are accepted only when Shopify lists the product in that collection, and the final Greek page passes the same host, status, path and product-handle checks. Collection checks are bounded to two specific paths and a five-second network timeout. The public pointer changes only after XML audit, unique-ID check, immutable Blob upload and hash verification, and now rejects a candidate with fewer items than the current preview.

Color variants keep separate variant IDs and share g:item_group_id for the Shopify parent. Zero-quantity CONTINUE remains eligible. Greek copy and colors are sourced from Shopify; known reversed color translations stay excluded.

## Remaining work

1. Expand reviewed FAVI Greece category mappings. The current 1,087 mapped products cover only part of 8,444 GR active and published products. Shopify taxonomy is present on 3,933; 4,511 lack a product category, so source catalog categorization is a separate blocker.
2. Fix Greek storefront address coverage. Only 298 of 1,087 mapped products have a verified GR page. Direct checks often return non-200; add or repair market routing and use verified URLs only.
3. Complete Greek product and variant translations, especially copy and color. Only 393 mapped products have both Greek title and description. Inspect source errors rather than relaxing locale checks. Sampled Greek pages also showed Bulgarian navigation.
4. Replace the completed source journal with recurring fresh catalog generations and an age guard. A worker restart currently recalculates from the same snapshot rather than newly created Shopify products.
5. Verify separate FAVI Greece registration, submit a complete reviewed feed, inspect their import feedback, and then switch the destination subscription. Petya's 2026-09-25 email mentioned a separate country registration and Greek trial; acceptance remains unverified.

The Bulgarian Google feed has 11,870 variant rows in its latest published generation. Comparing that with 246 Greek FAVI XML rows shows the scope gap, although the two channels apply different requirements. The Greek source has 12,556 variants, so source volume itself is not the limiting factor. The public Greek URL is for human review, not the completed FAVI Greece catalog.
