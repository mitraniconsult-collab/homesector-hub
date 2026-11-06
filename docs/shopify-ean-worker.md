# Shopify EAN barcode batch worker

Safely converts **only the barcode type** to `EAN` for valid EAN-8 and EAN-13 values in the connected Shopify store. No barcode values, prices, stock, templates, or product metadata are changed.

## Setup

Run on Node.js 20+ from the repository root. Configure the environment securely (never commit a token):

- `SHOPIFY_SHOP_DOMAIN=your-store.myshopify.com`
- `SHOPIFY_ADMIN_ACCESS_TOKEN` with `read_products` and `write_products`
- Optional: `SHOPIFY_API_VERSION=2026-10`

## Run

First preview one page of up to 50 variants, without modifying Shopify:

```bash
node scripts/shopify-ean-batch.mjs --max-pages 1 --checkpoint ./ean-preview.json
```

Then, after reviewing the expected scope, write one page with at most four concurrent **per-product** requests:

```bash
node scripts/shopify-ean-batch.mjs --apply --workers 4 --max-pages 1 --checkpoint ./ean-live.json
```

Continue with the **same checkpoint** and a higher page limit:

```bash
node scripts/shopify-ean-batch.mjs --apply --workers 4 --max-pages 10000 --checkpoint ./ean-live.json
```

Store checkpoint and logs outside the Git repository for production runs. A persistent filesystem is required for reliable resume after deployment restarts.

## Safety rules

- Validates EAN-8 and EAN-13 length, digits, and checksum.
- Leaves blank, non-EAN, and mixed-format barcode lists unchanged.
- Avoids changing a variant when Shopify has already set all its codes to EAN.
- Reads at most 50 variants per page; groups mutation requests by product.
- Uses bounded concurrency, backoff and retry for rate limits and temporary failures.
- Writes a checkpoint after each page. Failed pages do not advance the cursor and can be retried.
- Runs in read-only preview mode unless `--apply` is explicitly provided.
- Changes are not scheduled automatically; an operator must explicitly run the live command.

Note: `eligible` and `updated` in the dry-run report describe **would-be** changes, not actual writes. After a live operation, verify representative barcodes in Shopify admin and with an independent read-back query.
