# Homesector Feed Manager — staging checklist

Status: NOT DEPLOYED. Do not replace Feedhub yet.

## Target matrix
- BG / RO / GR / HU
- Google Merchant Center, Meta, FAVI, Biano
- Enable only market/channel combinations supported by the corresponding account.
- Each target needs its own accepted schema and feed URL. The current generic XML serializer is **not** sufficient for FAVI or Biano production submissions.

## Required integration
1. Read Shopify Admin catalog with `feeds/shopify_catalog.py`.
2. Resolve market publication, localized titles/descriptions, URLs, contextual prices, currencies, taxes and variant availability using Shopify Markets / contextual GraphQL. Never derive currencies from a fixed FX rate.
3. Map variants to normalized rows; validate image resolution and product URL; deduplicate by variant ID.
4. Implement channel-specific serializers and validate mandatory fields against platform specifications.
5. Generate to temporary file, validate XML and counts, atomically publish only after checks pass.
6. Keep last known good export and record generated_at, item counts, exclusions, error reasons and checksum.
7. Add authenticated manual refresh, scheduled regeneration and health endpoint. Public XML routes must be read-only.
8. Test sample feeds in each destination platform; switch from Feedhub only after acceptance.

## Configuration / user-supplied details
- Confirm Shopify custom app with read_products, read_publications, read_markets, read_inventory permissions as required by actual GraphQL queries.
- Store SHOPIFY_ADMIN_ACCESS_TOKEN in Render environment only; never commit or send in chat.
- Confirm destination account/catalog IDs and allowed countries for each platform.
- Confirm domains and whether RO checkout uses RON and HU uses HUF in live Shopify Markets.
- Confirm policies for out-of-stock, preorder, shipping, and excluded collections.

## Safety
- Work on feature/feed-manager-audit until review.
- No deployment or replacement of active feeds without sample acceptance.
