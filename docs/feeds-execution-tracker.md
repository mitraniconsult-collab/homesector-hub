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
