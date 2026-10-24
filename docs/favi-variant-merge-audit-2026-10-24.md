# FAVI variant grouping audit — 2026-10-24

Scope: live RO preview warnings and Shopify Admin product/variant records. The RO preview has 155 indistinguishable variant-group warnings; those warnings are not a count of wrongly merged products. Two passes inspected roughly 50 warning groups against live Shopify Admin data and confirmed eight mixed-model/type Shopify parents. The public RO XML is unchanged; these are source-data findings, not yet applied fixes.

| Shopify product ID | Handle | Variant SKUs | Finding |
| --- | --- | --- | --- |
| 10099417841931 | `vaza-atmosphera-sao-kieramika-20-cm` | 155614A / 155614 | Sao ceramic vase and Apolon marble vase are separate models/materials. |
| 10099423117579 | `vaza-atmosphera-soa-17-5-cm` | 155613A / 155613 | Sao and Contemporary vases are separate models. |
| 10168011161867 | `noshchno-shkafchie-atmosphera-koval` | 166504B / 166504C | Koval and Ajay bedside tables are separate models. |
| 10168193155339 | `skrin-atmosphera-koval` | 166506B / 166506C | Koval and Ajay dressers are separate models. |
| 10150408225035 | `matrak-za-pod-atmosphera-dolce-riviera-60x180-cm` | 194337D / 194337A | Dolce Riviera and Indie floor mattresses are separate models. |
| 10675346342155 | `krieslo-atmosphera-leone` | 202214D/B/A/E / 202214H | Four Leone colors share a parent with one Nyero chair. Preserve the Leone color group; move Nyero to its own parent/group. |
| 10685748871435 | `kilim-atmosphera-waste-miks` | 209100A / 209101A / 209101C | Waste rugs in two sizes share a parent with a Cherry rug. Keep Waste sizes grouped; separate Cherry. |
| 10693648908555 | `diekorativna-vzghlavnitsa-atmosphera-35x75-cm-brodieriia` | 212428H/I/J/K / 212428M | Hary embroidery designs share a parent with an Arty pillow. Check whether Hary designs remain one family; separate Arty. |

Second-pass likely valid groups: Kim mirror sizes (203587/203589/206405), Desy pendant colors (157860/157860A), Esra and Rondo rug sizes (164013/156147 and 194339/194340), Ilanga rug colors and sizes (209036A/B, 209037A/B), and 5five double-lid bin sizes (186222/164737/164738). These need localized variant labels to reduce warnings, not separate parents.\n\nAdditional review before changing Shopify:
- Product 10085136302347: SKU 157282E says Dario armchair cover; 157282D says Dario armchair. Confirm source images and whether the first title is incorrect.
- Product 8835533406475: SKU 102544 is Cali photo frame; 102544A is Cali nine-photo collage frame. Confirm whether these are separate products or intended sizes/styles.
- Products 10674425561355 and 10674425921803: Linah cushion parents contain variant option model fragments `nah` and `lou` (possibly Lilou) and different dimensions. Verify original supplier SKUs before splitting.
- Product 10692885971211: SKU 212701C has `n Modul` while 212701A/B have `& Modul Zebra`; the first string may be truncated. Verify supplier model before splitting.
- Product 10696412299531: SKU 155530A is a 24 cm wood Zely lamp; 155530X is a 23 cm black metal mesh Zely lamp. Verify whether this is one model with material variants or two designs.
- Product 10696974991627: Tiana framed artwork variant 179508 says canvas, while 179508A says vase. This may describe the pictured motif; check images before splitting.

Valid warning example: product 10084976689419, Lenia coffee table SKUs 197894A/B, differs by glass finish and should remain a variant family. Its warning needs localized variant detail, not a product split.

Any Shopify split must preserve variant SKU, inventory item, price, image, market publication, translations, collection memberships, and redirects. Keep public XML paths, item IDs, and variant links stable where possible. FAVI subscriptions are outside this audit and remain untouched.
