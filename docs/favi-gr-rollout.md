# FAVI Greece rollout status (2026-10-21)

## Public partial preview

- XML: https://hub.homesector.bg/feeds/favi/GR-preview.xml
- Diagnostics: https://hub.homesector.bg/feeds/favi/GR-preview-report.json
- Protected Hub dashboard: https://hub.homesector.bg/feeds
- Verified public HTTP 200 after the exact-ID correction: 667 XML items, 667 distinct variant IDs, EUR prices, SHA-256 `1144ec60924487be25d0204f711226c7c9601f9fb4c19b8bd043d994977b11a3`.
- This is a partial, noindex preview. `approved_by_favi=false`; no FAVI destination subscription was changed.

The fresh Shopify snapshot at 2026-10-21 18:13 UTC contains 19,303 products, of which 9,029 are active and published to Greece with 13,141 source variants. The public report was built with twenty-five reviewed exact taxonomy mappings covering 2,493 products. Ten more exact mappings are deployed for the next scan; from the same snapshot they could cover another 1,136 active products, bringing mapped coverage to approximately 3,629 before other gates. Greek title and description exist for 1,626 mapped products. Direct Greek URLs verified for 401 mapped products and collection-context URLs for another 225, totaling 626 distinct verified product URLs. These gates yielded 668 variants at 18:35 UTC. A one-off correction at 18:42 UTC removed the single miscategorized coffee grinder from the public preview, leaving 667. The report's source coverage counters still describe the 18:13 snapshot; its `manual_correction` records the exact removal.

The Shopify Product categories for coffee grinder `8730408747275` and jar tongs `10980173709579` have since been fixed to Coffee Grinders and Tongs, respectively. The next fresh scan will pick them up. The correction is pinned to the old preview hash and cannot remove a row from later generations.

The URL verifier requires a 200 HTML page at the exact expected Greek product path and checks Shopify collection membership for collection-context links. The next staging scan will report distinct `http_404`, `http_429`, etc. rather than the previous combined `non_200` counter. It will not relax admission. The staged generation now checkpoints completed translation and URL batches and yields before the Bulgarian Google cycle; partial XML is never published. The public pointer changes only after complete XML audit, unique-ID check, immutable upload, hash verification and count guard.

Color variants retain distinct variant IDs and share `g:item_group_id` for their Shopify parent. Zero-quantity variants with CONTINUE remain eligible. Greek copy and variant colors are sourced from Shopify; known reversed color translations remain excluded.

## Remaining work

1. Expand reviewed FAVI Greek taxonomy mappings after measuring the new ten on a fresh run. The 2,493 mapped products in the public report cover only part of 9,029 active Greek products; the new mappings could raise this to approximately 3,629. Do not infer a FAVI category from unverified names.
2. Diagnose the 2,092 direct URL checks that returned non-200 in this snapshot, using the exact HTTP status breakdown from the next scan. Fix Greek storefront routing or transient failures while keeping verified live URLs as the gate.
3. Complete Greek title, description and variant-color translations. Of the 2,493 mapped products, only 1,626 have both Greek title and description; draft review batches for Food Storage (20) and Outdoor Dining Tables (10) have not been written to Shopify.
4. Run the next fresh, resumable Greek scan to reflect corrected Shopify categories and new diagnostics; review coverage and XML audit before expanding the public preview.
5. Confirm a separate FAVI Greece registration, submit a complete reviewed feed, inspect import feedback and then switch the destination subscription. Petya's 2026-09-25 email mentioned a separate country registration and Greek trial; acceptance remains unverified.

The Bulgarian Google feed published 12,046 variant rows at 18:41 UTC. Its comparison with Feedhub's 11,169 rows has 10,581 matched IDs, 1,465 only on our side and 588 only on Feedhub's. These are different channels with different admission rules, so the 667-vs-12,046 gap is a coverage target, not proof that Shopify lacks Greek variants.
