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

The module currently has **no full GR source-catalog job, no mounted XML publication,
and no public FAVI GR URL**. Never describe the private helper as a submitted feed.
Next work: restartable full GR catalog journal, verified Greek product URL checks,
category coverage audit, destination acceptance and a stable hosted preview URL.

## Verification

Three Greek FAVI candidate regression checks passed locally with Python: grouped
variants and CONTINUE, reversed Greek color hold, and URL/category gates. Existing
three international market-row and nine FAVI serializer checks also passed. A generated\nGreek RSS candidate passed the common XML audit. The changes are on
`feature/feeds-other-channels`; not deployed or submitted to FAVI Greece.
