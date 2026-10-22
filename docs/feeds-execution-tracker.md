# Homesector Feed Manager — execution tracker

Updated: 2026-10-22. Latest checkpoint below supersedes older historical entries.

## Latest checkpoint — 2026-10-22 12:40 UTC

- Worker `srv-dbbm4fom7kps73fecs40` is live at `6a9283d594b39fc931fc527a3ab3805b48fac4fb`.
  The 1 GB persistent volume filled during the 13,227-item BG refresh: all three
  jobs reported `OSError` after 12:05 UTC. Safe retention removed two completed
  old BG run folders at 12:38:54 UTC, preserving the active and last published
  generations. The resumed BG run published its comparison at 12:40:21 UTC,
  SHA256 `305f629f85747ceb47790d3a3cca13b6146f3ddd95655cb71cee9afe32447d50`,
  with 13,227 variants and no content issues. FAVI BG private preview grew from
  85 to 894 items; its ID/category/backorder gates and FAVI approval still apply.
- GR active source journal contains 19,303 products; direct URL checkpoint 920.
  Public report still reflects the 2026-10-21 2,025-item preview. RO source
  journal contains 19,303 products, translations are complete, URL checkpoint
  220; public report remains 503 until private audit and explicit preview gate.
  Both scans must resume after BG and finish before the six-hour source age
  guard; do not publish a stale generation merely to increase item count.
- HU private builder and tests are committed, but not scheduled/deployed. FAVI BG
  remains private. Google BG is retained as the shared source/diagnostic, and
  the Hub UI now labels it accordingly; it is not a FAVI BG submission URL.
- FAVI email evidence: on 2026-05-14 Homesector sent the current supplied
  Feedhub Google URL to Petya as a FAVI feed, but FAVI described converting the
  supplied XML internally in an earlier 2026-01-27 email. Therefore the
  source IDs are useful continuity candidates, not proven internal FAVI IDs.
  Avoid silently migrating punctuated legacy IDs. User will submit finished
  feeds; this project has not changed FAVI subscriptions.

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


## 2026-10-20 — public Google BG comparison URL delivered
- Production Hub main commit 26219f8c70e459dcfdfeb5e1863dfc19463cff4f adds public private-Blob-backed routes: https://hub.homesector.bg/feeds/google/BG.xml and https://hub.homesector.bg/feeds/google/BG-comparison.json. Full Next production build and actual public HTTP 200 verified.
- Durable worker commit 0aead9303fee44749b5e0348369b26aa29893239 publishes immutable XML/report snapshots, verifies both by readback, and updates the current pointer last using conditional storage ETag. Old public snapshot survives failed uploads. These URLs are comparison candidates; destination subscriptions were not switched.
- Exact existing Feedhub URL recovered from the owner's prior sent Feed email, then explicitly confirmed by owner: https://feedhub-storage.onecommerce.io/do/data_feed/google_feed/25c5f6d4b8f0f8c28afcfa046b823d03.xml . Configured FEED_REFERENCE_AUDIT_URL on the existing worker; no credentials committed or printed.
- Initial real comparison at 19:21:55 UTC: Feedhub 11,169; ours 11,461; matched 10,581; only Feedhub 588; only ours 880. All 10,581 matched historical IDs retained, zero ambiguous matches and duplicate IDs. Independently downloaded public XML SHA256 376a56c5c6f41fa80f63bc8ad55674b25e8382a1b33c9ed346fcb6779fd2e42f matches the public report.
- Initial field differences: 5,148 titles, 273 prices, 852 availability, 12 images. Feedhub-only rows comprise 584 out-of-stock plus 4 marked in-stock. Live Shopify reads of all 4 Feedhub-only in-stock variants show quantity 0 / DENY, so they are not zero-stock CONTINUE omissions. Two out-of-stock examples also confirmed quantity 0 / DENY. This is a sample check, not a full 588-row source audit.
- Price canary: variant 53089265549579 has Shopify BG contextual price 690 EUR, matching ours vs Feedhub 739 EUR. Do not assume every difference is an error in either feed without checking Shopify.
- Follow-up commit 336d9d3330bc27226d32dbd4f73bdf16cb809338 refreshes current BG contextual prices and full variant display names during the inventory batch, and preserves BG variant names in future catalog scans. Missing/invalid current price stops publication. 76 feed regression tests pass.
- Outstanding for production replacement: 44 missing descriptions, review remaining source/content differences, recurring complete catalog regeneration (current comparison refresh runs at worker startup), storefront/delivery consistency, and destination acceptance. The existing Feedhub registrations remain active.

- Final verified public release at 2026-10-20T19:25:31.182336+00:00: 11,461 unique offers, SHA256 c981e8e636e2b0c51d898660dc70fd24c75b47acfb46158cb123869c9db8fd34. Independent public-download comparison confirms **zero title differences** after retaining variant names. Remaining differences: 273 prices, 852 availability, 12 images. All current BG prices were read from Shopify during this run; the 273 differences are vs Feedhub, not failures against Shopify. Missing descriptions remain 44. Worker deployment dep-dbbrvhbl550s73e0uq00 LIVE; complete refresh retained all 7,915 non-positive-quantity CONTINUE records.


## 2026-10-20 — hourly full BG regeneration and source description repairs
- Added scheduled_google.py to the existing mounted Render background worker, enabled FEED_GOOGLE_SCHEDULED_ENABLED=yes and FEED_GOOGLE_REGENERATE_SECONDS=3600. No new paid service was created.
- Every cycle starts a new complete ACTIVE/BG-context catalog, including new offers and excluding no-longer-eligible rows. Each generation has a separate fsynced JSONL journal, resumable Shopify cursor, and durable scheduler state. Page boundaries and a single-writer lock survive restarts/deploys. Hourly interval starts after successful completion; failed runs retain the same generation and retry after five minutes.
- BG-only catalog query reads 25 products and five variants per page with complete additional-variant pagination. Read-only live Shopify canary succeeded. Added HTTP-200 THROTTLED retries using Shopify cost metadata. Last source check refreshes inventory, prices, arrival dates, descriptions, ACTIVE status and BG publication.
- Public pointer updates only after full-catalog completion, duplicate/empty checks, a >20% catalog-decline guard, and immutable XML/report Blob readback. A failed/incomplete run leaves the previous public XML available. Keep three completed local generations; original audit archives remain separate.
- Initial live run exposed an undefined BG scope when requesting a sixth variant; fixed c6ced0b962b62ba1c562760df150c47f3f5f72f3 and added a regression covering BG-only and international variant pagination. Checkpoint at 600 products was retained and the same generation resumed after deployment.
- Checked all 44 missing-description variants directly in Shopify: 41 distinct products with empty descriptions. Feedhub has no usable description for these offers either.
- Matched 38 products unambiguously by exact SKU in Decoration Brands and fetched their product specifications. Wrote concise BG descriptions with supported purpose, actual dimensions/materials or volume only; no invented weather protection, lead times, prices, or included accessories. Read back all 38 changes successfully. Full before/after/source evidence: docs/feeds-description-repairs-2026-10-20.json.
- Remaining 6 variants belong to 3 products without a verified supplier match: 221855/221855A (Soletia table), 222387/222387A (Neiria double planter), 222386/222386A (planter). Kept included and descriptions empty pending source verification. Existing descriptions outside this repair list were not edited.
- Final source-refresh commit 0c181d7ee62d1d7ecc1143febd093971a68156cf; 85 isolated feed regression tests pass. Destination subscriptions remain unchanged. Public full-cycle verification recorded below after completion.

- **Verified first complete scheduled cycle**: Render commit 0c181d7ee62d1d7ecc1143febd093971a68156cf and deployment dep-dbbs6svf3r2c73bktfkg LIVE. Generation 55e70e7a54114ae58248ced8be2c9d74 resumed across deploys and published successfully at 2026-10-20 19:42:26 UTC. Public snapshot contains 11,461 items; SHA256 c1ff1ec08ff574ceda98414069f95706be56a7690171950638edd936c67d321d. Remaining common XML issue: six missing descriptions. Next full cycle persisted for 2026-10-20 20:42:26 UTC.
- Updated real Feedhub comparison: 11,169 legacy offers, 10,581 matched historical IDs preserved, 880 only ours, 588 only Feedhub. No title differences; remaining field differences 273 prices, 852 availability, 12 images. Existing destination subscriptions unchanged.
- Independent public download verified all 11,461 unique IDs, report/XML SHA agreement, exactly six missing descriptions, and HTTP 304 with the new ETag. Shopify readback confirmed all 38 descriptions match the intended content (only HTML whitespace normalization).
