# Unified availability and arrival sync

One Hub task: sync.py. The legacy sync_metafield.py delegates to it.
Never writes inventory quantities, product status, price, or publication.
Uses Shopify inventoryQuantity (aggregate available inventory) per tracked variant.

| Easyrea | Shopify quantity | Inventory policy | Expected arrival |
|---|---:|---|---|
| In stock (1) | any | CONTINUE | clear |
| In arrival (2) | >0 | DENY | clear |
| In arrival (2), valid future/today ISO date | <=0 | CONTINUE | supplier arrival date |
| In arrival (2), missing/invalid/past date | <=0 | DENY | clear |
| Confirmed stopped | any | DENY | clear |
| Missing/unknown status, untracked inventory | any | unchanged | unchanged |

STOPPED IDs must be confirmed from Easyrea and configured in EASYREA_STOPPED_STATUS_IDS. Recognized explicit stopped labels are also supported. Unknown IDs are not guessed. A real run aborts if over 25% of matching variants need review. Empty/incomplete supplier pages abort before writes. Only exact SKU matches for the configured Easyrea vendors are considered.

custom.expected_arrival is written per variant. The legacy product field is maintained only for a complete group with an identical date/no-date for every variant. Conflicts clear the product field and are reported; the storefront must read the selected variant field to show differing dates. Existing custom templates are preserved; only default/preorder are switched automatically.

Default is dry run. CSV report contains existing/target policies and dates, preserved quantity, reasons and review notes. Shopify mutation errors fail the job. Concurrent starts of the same task are rejected within one Worker process, including the legacy alias. Old standalone cron calls must not overlap.

This change does not install a new scheduler or Shopify inventory webhook. The rules are re-evaluated when the unified task runs. Inventory-change re-evaluation and the selected-variant theme display are follow-up integration work.

Verification: python -m unittest discover -s worker/tests -v
Required scopes: read_products, read_inventory, write_products.
Deployment: web and Worker must both use the new source bundle. Production Shopify sync has not been executed as part of publishing this change.
