# Product image jobs

The Shopify Operations page (`/shopify`, linked from Easyrea Sync) can scan active products with 0–2 images or quality concerns and run image recovery independently of ChatGPT and the browser. A test searches suppliers without AI calls or Shopify writes. Real mode uses exact SKU/EAN checks followed by OpenAI text + image validation before attaching original galleries from Decoration Brands. Products with multiple variants, uncertain identifiers, mismatched colors/models/sizes, or failed media remain in the CSV for review. Existing images, titles, categories, prices and publication status are preserved.

## Deployment

Deploy the web and Python Worker from the same commit. The existing Vercel install step overlays `patches/web` onto `src`, and Docker overlays `patches/worker`. No additional paid service or disk is required: the existing private Vercel Blob store persists the job manifest, progress, AI decisions and write intents.

Existing settings required:

- Web: private `BLOB_READ_WRITE_TOKEN` / connected Blob store and `HUB_WORKER_TOKEN`.
- Worker: `HUB_WORKER_TOKEN`, `SHOPIFY_STORE`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, and `OPENAI_API_KEY` for real mode.
- `OPENAI_PRODUCT_MODEL` selects the existing vision-capable OpenAI model (default remains `gpt-4o-mini`).
- Optional `HUB_IMAGE_STATE_URL` overrides `https://hub.homesector.bg/api/image-job-state`. Set it to the matching web deployment for staging workers so they cannot consume production jobs.

Worker health exposes `image_jobs_version: 1` and the configured OpenAI availability without exposing credentials. Verify these before starting a test of a small collection, then run real mode with a small limit and inspect the CSV and Shopify media.

## Recovery and concurrency

The Worker launches an image runner at startup. An ETag compare-and-swap lease fences concurrent workers; heartbeat renews every 30 seconds and takeover requires the previous 240-second lease to expire. Checkpoints are remote, not process memory or ephemeral filesystem files. Browser reloads read current status. A pause or cancellation prevents new steps; an already submitted upload may still complete.

Before every Shopify write, the full accepted URL set and write intent are persisted. Media receive stable alts based on SKU + source URL hash. On recovery an attempted write is reconciled against Shopify and never blindly repeated. Pending media are polled; missing results after three minutes become `REVIEW_UNCERTAIN`. Failed media are reported without deleting existing assets. A network failure or temporary API rate limit uses automatic backoff; invalid credentials, insufficient API credit, and invalid AI output block the run with a visible Resume action.

One current job and its complete CSV are retained. Starting another job replaces the previous terminal manifest; download its report first if needed. A paused/blocked job must be resumed or explicitly cancelled before a new run. Limits cap candidates, not scanned pages or exact API cost. Real mode may make up to three OpenAI calls per candidate due to validation retries. Default limit is 100; choose a smaller first run.

## Gallery quality (version 2)

New images come exclusively from Decoration Brands' original product galleries. Exact SKU/EAN matching is required. Products with 1–2 pictures are always inspected, not skipped. Larger galleries are screened using original dimensions and thumbnail edge statistics; suspected low resolution, blur and unreadable images are queued for full comparison. These local metrics are screening heuristics, not conclusive quality judgments.

Originals smaller than 800 px on their short edge are excluded. A low-resolution picture may be replaced only by an original at least 1000 px on its short edge and at least 25% larger; a blur replacement must have no lower resolution and at least 35% higher measured edge variance. OpenAI also compares the actual old and new pictures at high detail and must explicitly approve each exact media ID and replacement index. White backgrounds alone do not justify replacing an image. Good images are kept; exact pixel duplicates are filtered locally and near-duplicate views are rejected by AI. If no improvement is available, the gallery remains unchanged.

The accepted gallery, original media IDs/URLs/metrics and replacement plan are checkpointed before upload. All new images must be READY before cleanup starts. A variant using an old picture is reassigned first. Cleanup uses `fileUpdate.referencesToRemove` to detach only approved old files from the current product; it never deletes the files from Shopify Files or changes other product references. This requires the Worker app's `write_files` permission. If cleanup fails or is ambiguous, new pictures remain and the old files are retained for review. Original IDs and URLs are included in the CSV for recovery.

Up to 20 current images and 20 original source images can be compared per product; larger galleries stay for review. Category changes and product activation are outside this task.
