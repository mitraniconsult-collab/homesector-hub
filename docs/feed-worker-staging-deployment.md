# Homesector Feed Manager — standalone staging worker deployment plan

**Status: READY FOR REVIEW; NOT PROVISIONED.** The current production Hub and Feedhub must not be changed.

## Verified pricing (Render public pricing, 2026-10-20)

- Background Worker `0.5c-512mb`: **$7/month**.
- Persistent disk: **$0.25 per GB-month**; e.g., 1 GB = $0.25/month.
- Example baseline: **$7.25/month**, excluding usage above assumptions, taxes, bandwidth, and any separate account/workspace fees.
- **Render Cron cannot mount/access persistent disks.** Do not provision a Cron + disk combination.
- Sources: https://render.com/pricing , https://render.com/docs/disks , https://render.com/docs/cronjobs

## Resource separation and provision gate

Do this only after explicit owner budget approval:
1. Create a **new, isolated Render Background Worker** named `homesector-feed-worker-staging` using repo `mitraniconsult-collab/homesector-hub`, branch `feature/feeds-other-channels`. Do not reuse or alter production worker. 
2. Build: `bash scripts/render-worker-build.sh`.
3. Plan: `0.5c-512mb` ($7/month). Attach smallest practical persistent disk, initially 1 GB, at `/var/data/feeds`, with verified capacity and volume persistence.
4. Start command: `cd worker && python -m feeds.continuous_runner`.
5. Secrets sourced from the approved Homesector Shopify app, stored **only** in Render: `SHOPIFY_STORE`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET` (or pre-existing scoped Admin API token). Access read-only.
6. Additional environment:
   - `FEED_DURABLE_PATH=/var/data/feeds`
   - `FEED_DURABLE_STORAGE_CONFIRMED=yes` **only after the disk is mounted and verified**
   - `FEED_BG_JOB_ENABLED=yes` **only after QA and canary acceptance**
   - `FEED_JOB_PAGE_LIMIT=5` for initial canary; increase to 25 only after successful checkpoint recovery.
   - `FEED_RUN_INTERVAL_SECONDS=30`
7. Set alerts for worker crashes and missing checkpoint progress. Lockfile ensures one writer per mounted volume.
8. Prove resume: run 5-page canary, restart staging worker, verify increased `products` and unchanged previously exported rows; explicitly verify ID uniqueness before finalization.
9. Complete full BG audit, validate `google-bg-unpublished.xml` with XML parser, unique IDs, price/availability/image and channel schema, counts/exclusions, and compare Feedhub. Never submit to Google before approval.
10. Do not enable RO/GR/HU or FAVI/Meta/Biano until market URL, translations and category mappings pass validation.

## Reliability constraints

- `durable_journal.py` stores only page-complete checkpoints and refuses an obvious ephemeral directory. The env flag alone **cannot prove** the volume is actually durable; inspect disk configuration in Render before enabling.
- Existing `batch_job.py` writes one complete XML only after Shopify pagination reaches the last page. Partial rows are internal and must never be externally accessible.
- No Feedhub cutover, no production deployment, and no charged resource provisioning without the user's explicit approval of this budget.
- The current staging Free web service has no persistent volume; its prior audit stopped at 9,900 scanned / 8,611 items without COMPLETED.
- The new dedicated worker code is not yet validated on a real disk. Unit-test CI must be green before provisioning.
