# Greek product-copy review queue

The FAVI GR preview requires real Greek `title` and `body_html` translations in
Shopify. The current feed does not create or infer them. In a spot check of
50 GR-published food-storage products, 49 had no Greek Product translations;
another 50 storage-container products all had both fields. Fixes should be
targeted by taxonomy, then measured in the next feed report.

Run this read-only export on the feed worker against a **completed** GR source
journal. For a 20-row food-storage sample:

```sh
cd worker
python -m feeds.favi_gr_translation_review \
  --source-folder /var/data/feeds/favi-gr-source \
  --output /var/data/feeds/favi-gr-food-storage-review.csv \
  --taxonomy-id gid://shopify/TaxonomyCategory/hg-11-4-6 \
  --limit 20
```

If the source journal has rotated, pass the current completed generation folder
to `--source-folder`. The command prints counts and a private CSV path; it does
not print product copy or write to Shopify.

The CSV includes source title/HTML, the current Greek values, the Shopify
`translatableContent.digest` for each field, empty review columns and a
`PENDING` status. A reviewer fills the Greek review columns and checks the
meaning, HTML, product specifications, dimensions and brand. Existing valid
Greek fields are included for context and are not automatically replaced.

There is deliberately no import command. Before a later
`translationsRegister` mutation, re-fetch the source digests and existing
translations; reject any changed source or already-translated field, and write
only approved fields with the correct Greek locale. ProductVariant
`option1` color translations need their own review because the product-copy
export never modifies them. Keep the CSV on private storage; it is not a public
feed asset.

Shopify documentation: [translatableResource](https://shopify.dev/docs/api/admin-graphql/2026-07/queries/translatableResource),
[managing translated content](https://shopify.dev/docs/apps/build/markets/manage-translated-content).
