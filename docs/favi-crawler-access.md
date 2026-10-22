# FAVI storefront URL verification and HTTP 429

Shopify tightened bot limits on public online-store pages in May 2026. An
anonymous worker with a User-Agent can receive repeated 429s even when Admin
GraphQL pagination succeeds. Do not interpret a 429 as a missing product URL.

For each market domain, Shopify Admin > Online Store > Preferences > Crawler
access can create a merchant Web Bot Auth signature. Select the exact connected
domain (`homesector.gr`, `homesector.ro`, or `homesector.hu`), name it for the
Homesector feed worker, and note its expiration (at most three months). Store
the copied values only as Render secret environment variables:

| Domain | Render environment variables |
| --- | --- |
| homesector.gr | `FEED_CRAWLER_GR_SIGNATURE_INPUT`, `FEED_CRAWLER_GR_SIGNATURE` |
| homesector.ro | `FEED_CRAWLER_RO_SIGNATURE_INPUT`, `FEED_CRAWLER_RO_SIGNATURE` |
| homesector.hu | `FEED_CRAWLER_HU_SIGNATURE_INPUT`, `FEED_CRAWLER_HU_SIGNATURE` |

The worker adds `Signature-Agent: "https://shopify.com"` automatically and
never forwards a signature to another host on redirect. Both values must be
set together. A missing pair leaves the market unsigned and subject to the
strictest Shopify bot limit. Rotate values before expiration. Do not put the
signature in Git, logs, reports, XML, or chat.

Keep `FEED_STOREFRONT_MIN_INTERVAL_SECONDS=2` and
`FEED_STOREFRONT_429_COOLDOWN_SECONDS=900` for the first signed scan. Check
Render logs for absence of new 429s, then compare the complete private report
and XML audit before allowing the public preview pointer to move.

Shopify documentation:
https://shopify.dev/changelog/posts/bots-and-agents-should-identify-themselves-via-web-bot-auth
https://help.shopify.com/en/manual/promoting-marketing/seo/crawling-your-store
