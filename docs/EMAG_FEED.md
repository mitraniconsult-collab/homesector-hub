# eMAG Bulgaria XML feed — deployment and release checklist

## Permanent feed URL

Eight stable public URLs, one feed registration per URL:

- `https://hub.homesector.bg/feeds/emag/BG.xml`
- `https://hub.homesector.bg/feeds/emag/BG-02.xml`
- `https://hub.homesector.bg/feeds/emag/BG-03.xml`
- `https://hub.homesector.bg/feeds/emag/BG-04.xml`
- `https://hub.homesector.bg/feeds/emag/BG-05.xml`
- `https://hub.homesector.bg/feeds/emag/BG-06.xml`
- `https://hub.homesector.bg/feeds/emag/BG-07.xml`
- `https://hub.homesector.bg/feeds/emag/BG-08.xml`

Categories are placed into shards by a stable SHA-256 hash of the normalized
category name. Products in one Shopify category always share a feed; adding
products in other categories never moves them to a different URL. Each feed
is separately checked for <=150 categories, <=100,000 items and <=100MB.

This is the **Publish products** XML feed, not an offer-update feed. The URL serves
the last complete, validated private Blob snapshot and returns HTTP 503 until
the first approved publication. No request to eMAG is made by this system.

## Prerequisites on Vercel

Configure on the web deployment (not only on the Python worker):

- `SHOPIFY_STORE`: exact `*.myshopify.com` domain.
- `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`: existing authorized Shopify app.
- `BLOB_READ_WRITE_TOKEN`: private Blob store containing feed snapshots.
- `EMAG_FEED_REFRESH_TOKEN`: dedicated high-entropy secret for the refresh route.
- `EMAG_VAT_PERCENT`: e.g. `20` if the BG Shopify price includes 20% VAT.
- `EMAG_HANDLING_DAYS`: verified processing days, `0`–`60`.
- `EMAG_FEED_PUBLISH_ENABLED`: default omitted/false. **Only set to `true` after release review.**

The generator assumes Shopify `variant.price` is a **VAT-inclusive BGN/EUR
merchant price in the currency used for eMAG BG**. Verify the shop currency and
tax configuration first; the exporter currently does not convert currencies
or apply a marketplace-specific markup. The release flag must remain disabled
until these checks and eMAG offer ID reconciliation pass.

## Manual refresh, after explicit approval

`POST https://hub.homesector.bg/api/feeds/emag/refresh`

Header: `Authorization: Bearer <EMAG_FEED_REFRESH_TOKEN>`

The refresh queries every Shopify variant, emits only active, eligible variants,
checks limits separately on eight category-based shards, writes all immutable XML
snapshots, and finally advances one shared manifest pointer. A failed refresh
keeps the previous complete set. An authorized scheduler can invoke the endpoint.

## eMAG seller UI

1. Products → Feeds → Add feed.
2. Feed type: XML; Feed model: **Publish products**.
3. Register all eight permanent URLs as separate feeds; validate each one after first generation.
4. Set default VAT and handling time to the same validated values as in Hub.
5. Map XML fields:

| XML field | eMAG field |
| --- | --- |
| `category` | Category |
| `product_name` | Product name |
| `brand` | Brand |
| `product_id` | Product ID |
| `product_code` | Product code |
| `product_url` | Product URL |
| `image_url` | Image URL |
| `sale_price` | Sale price (ex VAT) |
| `stock` | Stock |
| `description` | Description |
| `ean` | EAN |
| `vat` | VAT |
| `handling_time` | Handling time |

6. Map Shopify categories to eMAG categories in seller UI. Only categories
   enabled in the seller contract can be selected.
7. Validate a small selection of new and existing SKUs/EANs and inspect import
   results before enabling automatic daily schedules.

## Outstanding release blockers

- Reconcile IDs for existing eMAG offers; using a new Shopify variant ID for
  an existing offer may create duplicates or conflict with existing mappings.
- Validate category mapping, translated descriptions and eMAG requirements.
- Verify tax-inclusive pricing/currency and separate eMAG markup.
- Decide treatment of supplier stock and handling time (Shopify quantity 0
  is currently published as stock 0, not a presumed supplier quantity).
- Add a separate update-offers feed URL and reconciliation layer.
- Add automated refresh scheduling and freshness/quality monitoring.

The first-phase Shopify audit remains read-only and can be run under Easyrea
as `emag_catalog.py` to see missing images/SKU/EAN/category and duplicates.
