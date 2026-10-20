# Homesector Feed Manager — execution tracker

Updated: 2026-10-20. This file tracks *verified facts* versus untested implementation.

## Current execution

| ID | Task | Status | Evidence / next gate |
| --- | --- | --- | --- |
| BG-01 | Shopify OAuth access and Markets permissions | VERIFIED | Render startup reported PRODUCTS, MARKET_PUBLICATION, MARKET_PRICING, INVENTORY = OK |
| BG-02 | Google BG five-product sample | VERIFIED | Render log: XML VALID, 3 items / 5 products |
| BG-03 | Full Google BG catalog audit | RUNNING / NOT VERIFIED COMPLETE | Staging deployed commit bed66f4. Last read: 3,900 products scanned; 3,734 candidate variants. Check for explicit COMPLETED or FAILED |
| BG-04 | Full feed compliance, sample merchant acceptance | BLOCKED BY BG-03 | Review exclusions, Google schema, variant and stock semantics; compare Feedhub before switching |
| CORE-01 | Handle >25 variants via Shopify GraphQL pagination | CODE DEPLOYED | Commit e419d8e; end-to-end large-variant fixture remains required |
| CORE-02 | Read translated titles/descriptions and market-correct handles | PARTIAL / UNTESTED | Shopify verified RO/EL/HU translations for a Quttin product; localization.py applies verified copy, but fetching at scale and URL checks are pending |
| CORE-03 | Validate market publication/pricing/inventory | VERIFIED ON SAMPLE | Shopify live query and Render startup checks OK |
| CORE-04 | Persistent storage, atomic publish, last known good | TODO | Current Render /tmp is ephemeral |
| CORE-05 | Retry/rate limit for full catalog | CODE DEPLOYED | bed66f4; audit progressed past earlier 2,600-product failure |
| QA-01 | Preflight gate per market and destination | IMPLEMENTED / UNTESTED | channel_quality.py, tests/test_feed_quality.py; feature branch only |
| FAVI-01 | Category mapping for FAVI | BLOCKED | Shopify productType is empty for real sample products; use Product category/collection taxonomy instead |
| META-01 | Meta schema and Merchant validation | TODO | Do not relabel Google XML as proven Meta feed |
| BIANO-01 | BG-specific Biano XML schema | TODO | Needs destination specification |
| RELEASE-01 | Replace Feedhub | BLOCKED | Require complete passing feed + destination acceptance + rollback |

## Channels in scope
- Google: BG, RO, GR, HU
- Meta: BG, RO, GR, HU
- FAVI: BG, RO, GR, HU
- Biano: BG

**Live publishing is OFF for all 13 new feeds. Feedhub remains on.**

## Operational monitoring
- Render service: homesector-worker-feed-staging / srv-dbbi158m7kps73f2gii0
- Diagnostic log patterns: `[feeds] BG full audit progress`, `COMPLETED`, `FAILED`.
- Task automation is NOT ACTIVE. The account has reached its active-task limit; never imply that push notifications were set.
- When the user authorizes pausing another task, create an hourly condition watcher and notify on completion/failure.

## Next implementation order
1. Verify full BG audit finished with no missing variants / API errors.
2. Persist auditable output outside ephemeral /tmp and add checksum / last-good retention.
3. Add true Shopify translated content with explicit locale verification and correct market URLs.
4. Map Shopify taxonomy/collections to FAVI categories; implement Meta and Biano serializers.
5. Test each destination and switch only upon user-approved rollout.
