# FAVI Greece: implementation checkpoint (2026-10-21)

## Confirmed inputs

- Shopify market GR is active for sampled Cleon and Quttin products; contextual price in EUR.
- Shopify product locale el supplies translated title and body_html on sampled products.
- Cleon has two Shopify variants sharing parent product 10685584408843. Its current Greek
  option1 translations are reversed against the source colors: variant 52135056081163
  is Кафяв but says Μπεζ; variant 52135056113931 is Бежов but says Καφέ.
  The Greece preflight excludes these rows until source translations are corrected.
- Petya's 2026-09-25 email states each country needs a separate FAVI registration and
  offers Greece as a free trial. Registration/acceptance has not been verified.
- The public homesector.gr Cleon product page currently has Greek product text but Bulgarian menu labels; resolve the market landing-page language before destination review.
- Greece product category paths must be detailed and Greek. The helper accepts an
  explicitly verified per-product category map; it does not translate BG categories.

## Code

`feeds.favi_gr_preview.create_preview` accepts complete Shopify product records
with contextual GR prices, an explicitly verified GR category map, confirmed Greek
landing-page product IDs, and Shopify product/variant translations. It returns private
Google RSS XML plus exclusion counts. Color variants keep unique IDs and share the
Shopify parent group ID. Zero-stock CONTINUE remains included.

A restartable full GR source-catalog scanner now exists at `feeds.favi_gr_catalog`.
It writes private XML and an exclusion report on the confirmed durable mount. It
can run in bounded batches beside the BG schedule with `FEED_FAVI_GR_SCAN=yes`,
but this flag is not enabled on the live worker. Verified input files on the mount
are `favi-gr-verified-categories.json` (product GID to `{market: GR, verified:
true, path: Greek category}`) and `favi-gr-verified-url-ids.json` (list of
verified product GIDs). Missing files deliberately yield exclusions, not
invented categories or links. There is **no public FAVI GR URL or submission**.
Next work: execute the complete GR scan, verify Greek product URL and category
coverage, correct reversed source color translations, and host a reviewed XML
for FAVI Greece's separate account acceptance.

## Verification

Three Greek FAVI candidate regression checks passed locally with Python: grouped
variants and CONTINUE, reversed Greek color hold, and URL/category gates. Existing
three international market-row and nine FAVI serializer checks also passed. A generated
Greek RSS candidate passed the common XML audit. The changes are deployed on the Render worker from `feature/feeds-other-channels` (commit `efea50b`). No full GR source job or public FAVI URL exists yet, and no feed was submitted to FAVI Greece.
