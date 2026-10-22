# Stable FAVI feed URLs

These are the canonical URLs that the merchant may submit to FAVI:

- Greece: `https://hub.homesector.bg/feeds/favi/GR-preview.xml`
- Romania: `https://hub.homesector.bg/feeds/favi/RO-preview.xml`

Do not rename, redirect behind authentication, or remove these routes when moving from preview to production. The public route stays fixed; each successful audited generation may atomically update its Blob pointer to a new immutable XML snapshot. The SHA/ETag, item count, and report content can change while the URL does not.

Keep the existing public response anonymous and HTTP 200 for feed consumers. Preserve stable item IDs and variant links. If a new feed version requires an incompatible format, retain these routes until FAVI has explicitly switched to a replacement URL.

HU and BG have no public FAVI XML URL approved by this record yet. Do not give their private artifacts to FAVI.
