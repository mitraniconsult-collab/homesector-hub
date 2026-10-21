# FAVI Greece: rollout checkpoint (2026-10-21)

Partial preview: https://hub.homesector.bg/feeds/favi/GR-preview.xml
Diagnostics: https://hub.homesector.bg/feeds/favi/GR-preview-report.json

The worker has scanned 19,303 Shopify products; 8,444 are active and published
in GR. Four checked Greek FAVI category mappings cover 594 products. Of these,
69 product URLs passed the homesector.gr landing-page check. The other 461
returned non-200; 64 redirected to another path. The first private XML candidate
has 65 audited items with unique IDs. The counts can change at publication.
The public endpoints are deliberately labeled partial_preview and noindex.

The worker reads contextual EUR prices and Shopify Greek translations. Distinct
color variant IDs share the Shopify parent as g:item_group_id, and CONTINUE
variants remain eligible at zero quantity. Reversed color translations on Cleon
are held until fixed. Exclusion counts overlap by reason: 11,733 candidate
variants lack a checked FAVI category, 12,473 lack a verified Greek URL, 3,004
lack verified localized copy, and 874 lack verified color. They are not
distinct product counts.

The publisher requires FEED_FAVI_GR_PREVIEW_PUBLISH=yes and a confirmed durable
mount. It audits nonempty XML and unique IDs, uploads immutable private Blob
snapshots, verifies downloads, then switches a separate FAVI GR pointer. This
does not alter the live Bulgarian Google feed or FAVI subscriptions.

For a complete feed, expand reviewed Greek category mappings; resolve Greek
product URLs and redirects; correct translations and storefront localization;
implement recurring fresh Shopify scans (the current journal is a snapshot);
then obtain FAVI Greece account acceptance. Petya's 2026-09-25 email mentioned
a separate registration per country and a Greek free trial, but registration
and acceptance remain unverified. Do not submit the partial preview as the
finished catalog.
