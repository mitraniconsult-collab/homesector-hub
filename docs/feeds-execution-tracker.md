# Homesector Feed Manager — execution tracker

Updated: 2026-10-20. This file tracks *verified facts* versus untested implementation.

## Current execution

| ID | Task | Status | Evidence / next gate |
| --- | --- | --- | --- |
| BG-01 | Shopify OAuth access and Markets permissions | VERIFIED | Render startup reported PRODUCTS, MARKET_PUBLICATION, MARKET_PRICING, INVENTORY = OK |
| BG-02 | Google BG five-product sample | VERIFIED | Render log: XML VALID, 3 items / 5 products |
| BG-03 | Full Google BG catalog audit | COMPLETE ON DURABLE WORKER | 19,305 products / 11,461 rows. XML content preflight is separate from export completion |
| BG-04 | Full feed compliance, sample merchant acceptance | BLOCKED BY BG-03 | Review exclusions, Google schema, variant and stock semantics; compare Feedhub before switching |
| CORE-01 | Handle >25 variants via Shopify GraphQL pagination | CODE DEPLOYED | Commit e419d8e; end-to-end large-variant fixture remains required |
| CORE-02 | Read translated titles/descriptions and market-correct handles | PARTIAL / UNTESTED | Shopify verified RO/EL/HU translations for a Quttin product; localization.py applies verified copy, but fetching at scale and URL checks are pending |
| CORE-03 | Validate market publication/pricing/inventory | VERIFIED ON SAMPLE | Shopify live query and Render startup checks OK |
| CORE-04 | Persistent storage, atomic publish, last known good | PARTIAL | Dedicated worker has mounted 1 GB disk; private snapshots persist. Shared API delivery and production last-good release remain TODO |
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


## Update 2026-10-20 13:04 Europe/Sofia
- **Monitoring enabled**: hourly Google BG completion/failure condition watch. Weekly Homesector Growth Audit paused with owner permission (not deleted).
- BG staging worker still deployed at commit bed66f4. Last observed progress log 2026-10-20 09:49:08 UTC: 3,900 products, 3,734 candidate entries; no COMPLETED/FAILED observed. Investigate if progress has stalled; do not mark completed.
- Channel quality gate and tests committed but **not deployed**; Meta XML draft and tests committed; still needs test execution and Commerce Manager sample validation.
- Verified Shopify Product.translations(locale:ro/el/hu) return localized title and body_html for one live Quttin product. localization.py applies verified supplied translations; full catalog fetching and verified international URL resolution remain pending.
- No new feeds published, Feedhub unchanged.

## Update 2026-10-20 — subsequent checkpoint

- Render staging at commit 95e7dfb is LIVE. Partial logs show **at least 5,400 scanned products**, no confirmed COMPLETE. Multiple previous deployment logs overlap; don't combine their counts. Worker now has local page-level cursor checkpoints but ephemeral disks are **not** durable across Render deployment.
- GitHub feature branch has candidate category mapping `category_mapping.py` using Shopify Product.category fullName / taxonomy ID; verified actual Shopify example with empty productType and category "Frying Pans". Translation is NOT inferred from English category.
- Quality gate now rejects wrong-country product domains and unverified non-BG FAVI category translations.
- Test files added for taxonomy candidate and validation. Tests not yet executed or deployed.
- Hourly completion/failure watch ACTIVE; Homesector Growth Audit is PAUSED with owner consent. No destination is connected or published.
- Next: inspect current staging logs for COMPLETED/FAILED, validate full XML, design persistent generation storage before first release.

## Update — 2026-10-20, latest execution check
- Render staging live at 95e7dfb. Latest progress 9,900 products / 8,611 candidate positions at 10:46:13 UTC; the Render worker logged "Shutting down" at 10:48:45 UTC. No confirmed audit COMPLETED/FAILED. Do not claim feed is complete or trigger another deploy without evaluating persistence.
- International feeds branch has new `feeds/shopify_translations.py`: read-only batched source of official Shopify title/body_html translations for RO/GR/HU, rejecting incomplete results. New offline unit tests included. Integration into the catalog/market links and deployment are still TODO; scripts untested on Render.
- Separate `category_mapping.py` and quality gate exist; verify platform taxonomy before release.
- No live feed switched or submitted. Feedhub remains unchanged.

## Progress update: BG interrupted; international pipeline expanded
- Live staging deploy remains 95e7dfb, no newer deploy on feed staging; most recent audited log: 9,900 products / 8,611 candidate items, then "Shutting down" at 10:48:45 UTC, **without COMPLETED or FAILED**. Final XML not confirmed. Avoid deployment of unrelated code to staging.
- International feed preparation implemented on separate branch in `shopify_translations.py` (read-only batching), `market_feed_rows.py` (locale normalization and fail-closed target preflight), with unit tests `test_shopify_translations.py` and `test_market_feed_rows.py`. These tests are code only, not yet executed on deployment.
- FAVI official guidelines: category must be in the corresponding market language and valid for FAVI's taxonomy; empty/general/foreign-language categories are rejected. Reference https://help.favionline.com/bg/значения-и-изисквания-към-отделните-елементи
- Market URL verification remains a blocking step before deploying RO/GR/HU feeds; current code requires explicit confirmation, not invented URLs.
- No new feed is live, current Feedhub unchanged.

## Update: root cause and additional work (2026-10-20)
- **Root cause identified (high confidence):** Render staging is a FREE web service and Render documents automatic spin-down after 15 minutes without *inbound traffic*, regardless of the long-running startup daemon; instance log shows shutdown ~15 minutes after startup and no audit COMPLETE. The local filesystem is discarded on spin-down. Source: https://render.com/docs/free . A persistent cursor on local disk does NOT provide recovery across spin-down/deploys.
- Release decision pending: use a separately executed job/background worker with durable storage and scoped credentials; Render Cron has a minimum $1 monthly charge and a 12-hour job limit: https://render.com/docs/cronjobs . Obtain owner approval before provisioning billed services.
- **FAVI corrections staged**: normalize Shopify GID to stable safe feed ID; reject all FAVI product_type category values not explicitly verified against target market category catalog (including Bulgarian).
- **Archival component staged but not wired**: `feeds/persistent_archive.py` supports HTTPS authenticated upload of finished XML and SHA256. Requires externally provisioned secure storage and credentials. Do not claim it persists any actual artifacts yet.
- Deploy branch `feature/feeds-other-channels` not connected to staging; no production feed submission. New tests are code only; CI execution still needed.
- BG audit last observed 9,900 scanned / 8,611 candidates before process shutdown; no complete XML to compare with Feedhub.

## 2026-10-20 14:06+03:00 onward — durable execution preparation

- Checked Render deployments and logs again: newest live commit 95e7dfb; full audit ended without COMPLETE after 9,900 products / 8,611 candidate rows. Production feeds untouched.
- Supabase account inspection: two unrelated projects (one inactive; one named "toy factory"). **Do not appropriate those stores for Homesector** without explicit ownership and scope approval. No Render Postgres or Key Value instance is available.
- New `feeds/durable_journal.py`: page-atomic append-only JSONL checkpoint; refuses ephemeral /tmp and requires `FEED_DURABLE_STORAGE_CONFIRMED=yes`. Durable storage must be an ACTUAL mounted persistent volume, not just a directory named durable.
- New `feeds/batch_job.py`: standalone, bounded 1..1000 Shopify pages per run; no ASGI startup thread; resumes at Shopify page cursor, handles extra variants, validates complete XML count and writes unpublished XML after the final page. Not deployed or executed against the store.
- New automated offline unit tests and CI workflow `.github/workflows/feed-manager-tests.yml` on branch changes. CI result not yet independently verified. Some related modules still need integration and destination/platform validation.
- Next gate: confirm exact monthly price and obtain approval for a properly persistent runtime + storage, then provision, set credentials securely, run small-page canary and verify checkpoint resume, follow with full audit. Do not configure existing Supabase projects by guess, switch Feedhub, or deploy to main.

## 2026-10-20 — priced deployment preparation
- Confirmed from Render docs: Cron Jobs **cannot** attach/access persistent disks; earlier Cron+disk proposal is superseded. The viable simple stack is dedicated Background Worker Starter $7/month plus 1 GB disk $0.25/month = **$7.25/month baseline** (excl. tax/overages). No paid resources authorized or created.
- Dedicated worker entrypoint `feeds/continuous_runner.py` committed: refuses missing confirmed disk, missing explicit enable flag, invalid page limit; enforces single writer via fcntl lock; runs bounded batches then parks on completed unpublished audit.
- Fixed missing `shopify_post` function on this branch, unifying bounded retry support for translations, product catalog, variant pagination and batch job.
- Wrote `docs/feed-worker-staging-deployment.md` describing exact build/start command, disk mount, QA canary and deployment safety.
- Tests/CI have been committed, but passing GitHub Actions results **have not been verified**. Real durable volume recovery test and fully compliant Google export remain pending.

## 2026-10-20 16:23+03:00 — REAL SHOPIFY CANARY PASSED, FULL BG RUNNING
- New paid Render Background Worker `srv-dbbm4fom7kps73fecs40`, persistent disk `dsk-dbbm5jrbc2fs73bld6l0` mounted at `/var/data/feeds`, Frankfurt, baseline ~$7.25/mo; old production worker and Feedhub unchanged.
- Verified `SAFE_IDLE disk_is_mount=True` and actual read-only Shopify OAuth with copied credentials.
- First 5-page canary processed 25 products, 24 eligible rows, status incomplete, no external publication.
- Redeployed and proved durable checkpoint restored: second 5-page canary resumed products **25→50** and rows **24→48**, rather than beginning again; unpublished.
- Changed `FEED_CANARY_ONLY=no`, page limit 200, interval 5 seconds; deploy `dep-dbbmlvoae00c739b6lq0` live, running full BG audit on mounted disk. Last captured BG progress **320 products / 236 rows**, no errors. Completion and full XML yet unverified.
- Hourly condition watcher redirected to new worker service ID, for completion/failure/stall.
- Still blocked on source/merchant validation and URL delivery for other 12 target feeds. Do not claim they are live or ready for cutover today without actual QA.

## 2026-10-20 — FAVI elevated to first priority
- User explicitly prioritizes FAVI. Execution order FAVI BG, then RO/HU; investigate if FAVI Greece currently operates before promising GR. FAVI's listed country category trees include BG/RO/HU but not GR (source: https://help.favionline.com/bg/значения-и-изисквания-към-отделните-елементи).
- Confirmed FAVI Google RSS requirements: detailed country-language product_type/category, unique and **stable historical product IDs** (FAVI warns identifier changes destroy history), unique product URL, full localized product detail, availability_date when backorder/preorder, EUR/RON/HUF context, valid images. Official docs: https://help.favionline.com/bg/значения-и-изисквания-към-отделните-елементи and https://help.favionline.com/bg/панел-за-управление-на-магазина .
- Fixed prior mistaken FAVI identifier validator accepting punctuation; new candidate IDs are alphanumeric only; optional verified historic-ID mapping takes precedence. **DO NOT cut over before retrieving current FAVI feed and retaining exact existing ID values.**
- Revised `favi_xml.py` to validate FAVI category verification, market locale and domain, stable safe IDs, availability dates, duplicate URLs; rejects noncompliant rows; added offline regression tests. These commits are feature-only and NOT deployed or independently executed.
- Separate Google BG durable worker still running (as of 13:43:22 UTC): 12,745 scanned Shopify products, 8,788 candidate entries; no confirmation of completed XML.
- Next user input required: URL of currently active FAVI BG feed or the FAVI dashboard XML Feed URL. Use this for ID continuity and compare categories before switching.

## 2026-10-20 FAVI BG measured deliverables (staging only)
- Google BG source finalized: 19,305 Shopify products; 11,461 eligible variant rows; SHA256 32eb87131674f405bb85f82bcc42d6f823c019f493e590526f870160ac1dc935.
- Legacy provided Feedhub Google XML: 11,169 rows, 10,581 URL-linked historical ID matches; 10,387 lacked BOTH google_product_category and product_type; 0 duplicate IDs. URL was user-provided; **not verified as current FAVI panel subscription**.
- New Shopify standard Product category census FINISHED read-only on persistent volume: 19,305 products; 18,819 assigned category; 486 unassigned; 678 distinct categories. Shopify Product type was empty in 10,727 of 11,461 Google BG variant rows, so it must NOT be used as primary mapping.
- FAVI public category page blocked Render (403). Read-only partial fallback taxonomy snapshot (47 paths) used solely for candidate auditing; 20 exact Product type leaf candidates; zero approved automatically. Source: https://favi.bg/partner-dashboard/category-list.
- Implemented explicit English standard Shopify taxonomy -> official Bulgarian FAVI category mapping; FAVI BG unpublished RSS preview created. After second mapping batch: **2,911 valid XML items** across 17 mappings (2,915 prepared, 4 excluded missing description); 2,777 IDs preserved from old Feedhub; 138 newly stable IDs; 8,546 omitted pending further verified category mappings. SHA256 c5b4d330e01d71adac85f95edcc4d0d4d67cb95f5647ef0e433c81a9d14a6e4d.
- Private staging report: /var/data/feeds/favi-bg-preview-report.json ; private feed: /var/data/feeds/favi-bg-unpublished.xml . Neither has publicly accessible URL and neither has been sent to FAVI. Generator checks duplicates/fields and excludes incomplete rows; FAVI has NOT accepted these XMLs.
- Next priority: extend verified category matrix for the remaining 8,546 candidate rows, inspect excluded descriptions, verify exact current FAVI subscription URL and FAVI platform category approval; then add durable read-only web hosting/auth and format preflight. Only after official FAVI validation and user approval may the live URL replace Feedhub.

## 2026-10-20 Strict Bulgarian FAVI preflight (latest)
- Read Bulgarian official instructions: https://help.favionline.com/bg/значения-и-изисквания-към-отделните-елементи . The BG requirements say ITEM_ID must consist of letters/digits without punctuation and Google 'backorder'/'preorder' require g:availability_date. Earlier permissive code was corrected; do not rely on prior 2,911-item preview as FAVI-ready.
- Six additional **proposed** Bulgarian category paths built from exact Shopify standard taxonomies: ornaments, Christmas village sets, decorative pillows, artificial trees, household storage boxes, tumblers. These are localized detailed proposals NOT validated/approved by FAVI.
- Hard migration guard now blocks an existing source product from silently receiving a new ID if the provided old Feedhub ID is disallowed. This XML was supplied as Google Feedhub, **not confirmed as active FAVI registered feed**, so platform's actual ID policy/history must be reviewed manually.
- Latest deployed private FAVI BG preview Render dep-dbbob3vavr4c73898hhg, SHA256 2f48328c5ade255a742930a7bb9656f5a29a24db768dcf59855a5abab72c1739: 85 valid rows, 135 candidate rows excluded missing backorder date, 3,731 rows held for existing-ID review, 7,510 rows without category mapping, 220 potential new-only ID rows examined. No external publishing.
- **Priority blockers**: (1) confirm current feed URL in FAVI panel and policy about existing punctuated legacy ID; (2) obtain trustworthy variant-specific availability dates from Shopify or exclude backorders; (3) expand precise localized category mapping and obtain FAVI approval; (4) current background worker is diagnostic only, no public XML URL. Never replace Feedhub until accepted and approved.


## 2026-10-20 — API branch reconciliation and snapshot quality audit
- Verified Render workspace previously confirmed by owner: tea-dardg6ojo6nc73fhnel0. API service follows feature/feed-manager-audit; durable worker follows feature/feeds-other-channels. API was live at 95e7dfb, worker at fb90074.
- Merged API checkpoint changes into the multichannel branch, retaining bounded retry handling and both durable/background and legacy diagnostic code paths.
- Legacy ASGI startup export now requires FEED_LEGACY_API_AUDIT_ENABLED=yes. Normal API wake-up no longer starts another full Shopify catalog scan on the ephemeral free instance.
- XML preflight now checks timezone-aware availability_date for backorder/preorder; serializer preserves supplied availability_date instead of discarding it. It never invents a supplier delivery date.
- Added durable feed-snapshot-diagnostics.json: per-snapshot checksum, timestamp, item count and XML quality issues for Google BG and FAVI BG. Original XML remains unchanged; local preflight is explicitly NOT destination acceptance or release readiness.
- Added authenticated /feeds/diagnostics; returns 503 if this service cannot access the actual mounted report. The background worker disk is NOT shared with the separate free API; an authenticated shared artifact store remains necessary for remote XML/report delivery.
- Deployment results and real catalog issue counts are recorded below only after verification.

- Verified deployment of commit 31bde6de475770387a06cf3bbbe56a0e5fa267cf: durable worker dep-dbbrg5rncjis73b149rg LIVE; API dep-dbbrgd3rjlhs73a8tp70 LIVE. Both branches share the same implementation.
- Actual durable Google BG snapshot preflight: **11,461 items; 7,913 missing/invalid backorder availability dates; 44 missing descriptions; 11,461 unique IDs**. Issue counts can overlap. SHA256 remains 32eb87131674f405bb85f82bcc42d6f823c019f493e590526f870160ac1dc935; original source unchanged.
- FAVI BG private snapshot has 85 items and passes common RSS checks, but FAVI category approval, historical ID review and external acceptance remain outstanding.
- Added a separate Google BG validated-preview XML builder: excludes failing entries with explicit reason counts, retains original IDs, validates the resulting XML again, and keeps original full export unchanged. This is a private candidate only, never an automatic replacement of a registered feed.


## Verified 2026-10-20 21:54 Europe/Sofia — valid private Google BG subset generated
- Commit eff5ed04b33a450bd955f369f21dd20881e811c6 is LIVE on both staging services: worker dep-dbbrh6tg1s2s73c2iso0; API dep-dbbrh6lg1s2s73a2q630.
- Actual mounted-disk generation completed: **3,548 Google BG entries pass local XML preflight**, **7,913 entries excluded**. The 44 missing descriptions overlap the excluded backorders; do not subtract twice.
- Private candidate: /var/data/feeds/google-bg/google-bg-validated-preview.xml; SHA256 2dcdf00b36776a2d3e15ef3df16e07a3b730669dc5ba7cd6c9045e54bbdd3355. Original full Google export and IDs remain unchanged. This is NOT merchant acceptance, public hosting, or an active feed.
- FAVI private preview still has 85 entries; 3,731 candidate entries remain held for legacy-ID review, 7,510 have no proposed category mapping, 135 new-ID candidates fail availability-date checks.
- 54 offline regression tests PASSED. New API /feeds/check returned HTTP 200 with API auth configured and legacy startup audit disabled; unauthenticated /feeds/status returned HTTP 401 as expected. Mounted worker report remains unavailable on the separate free API service, reported honestly.
- Remaining for first working Google BG feed: shared durable XML delivery with a stable HTTPS URL; scheduled fresh generation and last-good retention; destination trial/acceptance. Remaining FAVI inputs: actual active XML URL from FAVI panel, ID continuity, localized category completion/approval. Feedhub unchanged.


## 2026-10-20 — owner correction: zero warehouse stock + CONTINUE stays included
- Owner explicitly confirmed products at quantity 0 with Continue selling ON must remain in all relevant feeds. The previous 3,548-row subset is NOT the intended release catalog.
- Root cause: warehouse quantity was incorrectly used as the feed backorder status. Existing Hub easyrea/stock_rules.py distinguishes supplier IN_STOCK (CONTINUE, no expected_arrival) from supplier replenishment (CONTINUE with custom.expected_arrival).
- Central availability resolver now keeps physical `available` separately: quantity > 0 -> in_stock; quantity <= 0 and CONTINUE without expected arrival -> sellable supplier stock / in_stock; quantity <= 0 and CONTINUE with a real expected arrival -> backorder with the actual date; quantity <= 0 and DENY -> not sellable. No artificial availability date is invented.
- Read-only Shopify refresh resolves current inventoryPolicy, inventoryQuantity and custom.expected_arrival per variant. Product-level date fallback is allowed only for a product with exactly one variant. Original journal/XML and stable IDs are retained.
- Corrected full Google BG private XML and FAVI preview are generated from refreshed rows; quantity zero alone never excludes a CONTINUE row. Missing descriptions/categories/legacy IDs remain independent diagnostics, not a warehouse-stock exclusion policy.
- Live Shopify canary verified two zero-quantity CONTINUE variants without arrival dates, plus a zero-quantity DENY variant; node batch query executed successfully. 62 offline regression tests PASSED before deployment.
- Official docs checked: Google availability https://support.google.com/merchants/answer/6324448 ; FAVI BG requirements https://help.favionline.com/bg/значения-и-изисквания-към-отделните-елементи . Destination availability/dispatch promises still need to match the storefront and shipping configuration before release, especially FAVI's stock badge.


## Verified 2026-10-20 22:05 Europe/Sofia — warehouse-zero exclusion corrected
- Real Shopify refresh completed for all **11,461** original Google BG variant rows. Corrected full private XML retains all **11,461** rows, including **7,915** currently at non-positive warehouse quantity with CONTINUE enabled.
- Resolved availability: **10,549** sellable/local-or-supplier-stock entries; **912** genuine expected-arrival/backorder entries carrying their actual Shopify expected_arrival date. No missing availability-date errors remain. Warehouse quantities and stable IDs were not modified.
- Corrected full private XML SHA256 4d012b89813ce2465f2ee1a0f16e0cf86b6c2de0e2841578cfcc0e04de02a966. Retained independently from original journal/full XML.
- **11,417** entries now pass local common XML preflight. Remaining **44** missing descriptions are a separate content issue; they remain in the full source XML. Validated subset SHA256 8457f9d8f29d69aa6058397dba98ea9ab354e0e87139e33b839409b6e9885cc3. The old 3,548 subset is superseded and must not be offered as the intended catalog.
- FAVI private new-ID candidate rose from **85 to 220** entries; no serializer availability rejections remain. FAVI is still held on independent category coverage and historical-ID verification gates; no live subscription was changed.
- Added bounded HTTP-200 GraphQL throttle recovery; **63 offline regression tests pass**, plus an integration check proving that zero/negative-quantity CONTINUE records and real arrival dates survive full snapshot regeneration while original archives stay byte-identical.
- All new outputs remain unpublished. Stable public XML delivery, ongoing regeneration, storefront/shipping consistency and destination acceptance remain outstanding.
