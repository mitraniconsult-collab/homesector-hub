# Unified availability and arrival sync

One Hub task: sync.py. The legacy sync_metafield.py delegates to it.
Never writes inventory quantities, price, or publication; product status changes are separately gated.
Uses Shopify inventoryQuantity (aggregate available inventory) per tracked variant.

| Easyrea | Shopify quantity | Inventory policy | Expected arrival |
|---|---:|---|---|
| In stock (1) | any | CONTINUE | clear |
| In arrival (2) | >0 | DENY | clear |
| In arrival (2), valid future/today ISO date | <=0 | CONTINUE | supplier arrival date |
| In arrival (2), missing/invalid/past date | <=0 | DENY | clear |
| Confirmed stopped | any | DENY | clear |
| Missing from complete Easyrea snapshot | >0 | DENY; sell local stock only | clear |
| Missing from complete Easyrea snapshot | <=0 | DENY; consider product archival | clear |
| Unknown status, blank SKU, untracked inventory | any | unchanged | unchanged |

Easyrea status `0` means stopped. `1` means available. `2` means expected delivery. `EASYREA_STOPPED_STATUS_IDS` adds further confirmed IDs; `0` is always included. Unknown IDs, blank SKUs and untracked/unreadable inventory remain unchanged. A real run aborts if no actionable variants remain or if more than 25% of matched tracked variants have unknown statuses. Malformed supplier responses, repeated pages, and substantial count gaps abort before writes. A premature empty page is retried twice. After three empty responses, a row-count shortfall is tolerated only when it is at most both 0.1% of totalResults and 20 rows. Only exact SKU matches for the configured Easyrea vendors are considered.

MISSING is determined only against a complete validated supplier snapshot. It is processed immediately, not after a second sync. A missing variant's inventory policy becomes DENY, allowing only remaining Shopify stock to sell. Variants are never deleted. A multi-variant product stays active while at least one variant can sell; a complete product with a missing SKU and no sellable variants becomes an ARCHIVE candidate. Products manually marked DRAFT or ARCHIVED are never made active. Hub archives are tagged `hub-easyrea-auto-archived`, and only Hub-tagged archives can be restored if a sellable variant reappears. Incomplete product variant groups are not archived.

The CSV report includes planned product actions and statuses. Product archive/restore writes are disabled by default, and require `HUB_ENABLE_EASYREA_AUTO_ARCHIVE=true` after explicit dry-run review. A real run aborts before writes if the archive candidates exceed `HUB_MAX_EASYREA_AUTO_ARCHIVES` (default 100). No product or variant deletion is performed.

custom.expected_arrival is written per variant. The legacy product field is maintained only for a complete group with an identical date/no-date for every variant. Conflicts clear the product field and are reported; the storefront must read the selected variant field to show differing dates. Product templates are always preserved. The sync never writes templateSuffix, including default/preorder templates.

Default is dry run. CSV report contains existing/target policies and dates, preserved quantity, reasons and review notes. Shopify mutation errors fail the job. Concurrent starts of the same task are rejected within one Worker process, including the legacy alias. Old standalone cron calls must not overlap.

This change does not install a new scheduler or Shopify inventory webhook. The rules are re-evaluated when the unified task runs. Inventory-change re-evaluation and the selected-variant theme display are follow-up integration work.

Verification: python -m unittest discover -s worker/tests -v
Required scopes: read_products, read_inventory, write_products.
Deployment: web and Worker must both use the new source bundle. Production Shopify sync has not been executed as part of publishing this change.
