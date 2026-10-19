# Product image jobs

The Shopify Operations page (`/shopify`, linked from Easyrea Sync) can scan active products without media and run image recovery independently of ChatGPT and the browser. A test searches suppliers without AI calls or Shopify writes. Real mode uses exact SKU/EAN checks followed by OpenAI text + image validation before attaching original galleries from Decoration Brands. Products with multiple variants, uncertain identifiers, mismatched colors/models/sizes, or failed media remain in the CSV for review. Existing images, titles, categories, prices and publication status are preserved.

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

This initial task adds images only to products with no media. Low-resolution replacements, supplementing existing galleries, category correction and automatic product activation are outside this task.
