# FAVI Hungary private preview

The HU reader uses Shopify `publishedInContext(country: HU)` and
`contextualPricing(country: HU)`. A product without an actual HUF amount,
verified Hungarian title and description, exact FAVI.hu category, and
verified `homesector.hu` landing URL is excluded. Its variants retain unique
IDs and URLs and share the parent `item_group_id`. Zero-stock variants with
`inventoryPolicy=CONTINUE` remain sellable.

`feeds.scheduled_favi_hu.tick(mount)` writes a generation journal and the
completed private `favi-hu-private.xml` and `favi-hu-report.json` to the
confirmed durable feed disk. It never updates a public pointer. The running
GR/RO worker scheduler does not call the HU tick yet. Enable HU only after the
RO audit and capacity review; then separately build and review a public Blob
delivery route with the same SHA/count/pointer checks as RO.

The mapped leaves are checked against the current category list:
https://favi.hu/partner-dashboard/category-list . FAVI requires product copy
in the target language, precise accepted categories, and valid image and URL
paths. Its Google XML format uses unique `g:id` values and common
`g:item_group_id` for variants:
https://help.favionline.com/hu/%C3%A1ltal%C3%A1nos-inform%C3%A1ci%C3%B3k-az-xml-feedr%C5%91l
https://help.favionline.com/hu/egyedi-param%C3%A9terek-jelent%C3%A9se-%C3%A9s-k%C3%B6vetelm%C3%A9nyei

The current taxonomy map is intentionally limited to observed exact leaves.
Missing category mappings and untranslated products will be counted in the
private report. The HU checkout tax configuration (27% VAT) requires separate
merchant review before any FAVI submission, because this worker reads the
Shopify market price and does not calculate VAT.
