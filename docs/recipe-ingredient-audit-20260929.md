# Recipe ingredient optionality audit (2026-09-29)

Scope: the 35 reviewed Malaysian recipes seeded by `p3q4r5s6t7u8`.
The original seed contains 267 ingredient rows: 142 required and 125 optional.
The later `v4w5x6y7z8a9` migration demoted another 20 rows: the actual
pre-release catalogue has **122 required and 145 optional**, reproduced on
both a fresh PostgreSQL migration chain and UAT. Every optional row was compared with its
recipe's cooking steps and identity. The user chose: ingredients explicitly
needed for the written method are required; salt and adjustable seasonings
remain optional.

## Proposed correction: 85 optional rows become required

| Food | Rows | Base amount per 2 servings | Reason |
| --- | ---: | ---: | --- |
| SF120 cooking oil | 33 | 10 g | Every recipe carrying oil fries, stir-fries or browns food; the butter-fried spinach and steamed egg do not carry oil. |
| SF069 garlic | 23 | 9 g | Explicitly fried, simmered or added by the cooking method. |
| SF056 onion | 13 | 110 g | Explicitly fried or chopped in the cooking method. |
| SF071 ginger | 8 | 10 g | Explicitly fried/chopped in the cooking method. |
| SF054 shallot | 5 | 30 g | Explicitly fried in the cooking method. |
| SF148 mustard seeds | 2 | 2 g | Explicitly fried for the mamak cabbage and dhal tempering. |
| SF060 dried chili | 1 | 5 g | Bihun goreng's only listed chili, explicitly fried in step 2. |

These are conservative cooking minimums, not measured consumption. The
migration enumerates the exact recipe/food pairs and is reversible. The
required-match and quantity-aware ranking will change accordingly; the card
badge continues to show all listed ingredients, not just required ones.

## Retained optional from the original seed: 40 rows in 23 recipes

All IDs below refer to the authoritative canonical food ledger. The twelve
recipes absent from this table have no remaining optional ingredient from
the original 125-row subset. See the additional legacy review below.

| Recipe | Remaining optional ingredients | Why optional |
| --- | --- | --- |
| Bihun Goreng | SF151 salt | Adjustable seasoning. |
| Mamak-Style Cabbage Stir-Fry | SF064 green chili; SF151 salt | Adjustable heat/seasoning. |
| Cauliflower Stir-Fry | SF077 carrot | Extra vegetable, absent from steps. |
| Dhal Curry with Rice | SF064 green chili; SF136 chili powder; SF151 salt | Adjustable heat/seasoning. |
| Egg and Potato Curry with Rice | SF058 red chili; SF151 salt | Adjustable heat/seasoning. |
| Garlic Long Beans | SF151 salt | Adjustable seasoning. |
| Garlic Spinach Stir-Fry | SF098 lime; SF151 salt | Optional finishing acid/seasoning. |
| Long Beans with Egg | SF061 bird's-eye chili; SF151 salt | Adjustable heat/seasoning. |
| Malay Chicken Soup | SF072 tomato; SF151 salt | Tomato not called for by steps; adjustable seasoning. |
| Malaysian Chicken Curry with Rice | SF072 tomato; SF018 egg; SF151 salt | Tomato and egg absent from steps; adjustable seasoning. |
| Mixed Cabbage Stir-Fry | SF058 red chili; SF151 salt | Adjustable heat/seasoning. |
| Onion Omelette | SF151 salt | Adjustable seasoning. |
| Potato and Onion Stir-Fry | SF151 salt | Adjustable seasoning. |
| Sambal Eggplant with Rice | SF118 sugar | Sweetness optional; steps do not require it. |
| Sardine Sambal with Rice | SF058 red chili | Chili sauce is already the required heat source. |
| Soy Sauce Chicken with Rice | SF058 red chili; SF141 star anise; SF146 cinnamon; SF151 salt | Optional spice variation/seasoning; absent from steps. |
| Soy Sauce Squid | SF061 bird's-eye chili | Adjustable heat; absent from steps. |
| Steamed Egg | SF151 salt | Adjustable seasoning; no oil is listed. |
| Tofu and Prawn Stir-Fry | SF118 sugar | Sweetness optional; absent from steps. |
| Tomato Chicken with Rice | SF060 dried chili; SF118 sugar; SF151 salt | Step explicitly calls dried chili optional; sweetness/seasoning adjustable. |
| Tomato Egg Stir-Fry | SF118 sugar; SF151 salt | Adjustable sweetness/seasoning. |
| Tomato Tofu with Rice | SF151 salt | Adjustable seasoning. |
| Turmeric Chicken with Rice | SF133 curry powder; SF151 salt | Turmeric itself is required; curry powder is an optional variation. |

Audit boundaries: this does not claim that all recipes' ingredient quantities
are culinary-exact. The promoted amounts are minimums for matching and stock
sufficiency; a later recipe-specific cooking review can refine them. Ingredient
substitution is implemented separately; see `recipe-substitution-audit-20260929.md`.

## Additional legacy review: all 20 post-v4 seasoning rows

Approved by the user on 2026-09-29 after migration preflight exposed the
125-versus-145 discrepancy. This is reproducible migration history, not an
unexplained manual UAT edit. Migration `g3a4b5c6d7e8` follows the original
85-row correction and restores 15 essentials without changing their amounts.

| Recipe | Food / existing amount for 2 servings | Decision and cooking-step evidence |
| --- | --- | --- |
| Mamak-Style Cabbage | Turmeric SF135, 1 g | Required: step 2 fries turmeric with carrot. |
| Dhal Curry | Turmeric SF135, 1 g | Required: step 2 specifies turmeric for the curry base. |
| Egg and Potato Curry | Curry powder SF133, 16 g | Required: step 2 fries the curry base. |
| Garlic French Beans | Garlic SF069, 9 g | Required: step 1 fries garlic; defining ingredient. |
| Garlic Broccoli | Garlic SF069, 9 g | Required: step 1 fries garlic; defining ingredient. |
| Garlic Long Beans | Garlic SF069, 12 g | Required: step 1 fries garlic; defining ingredient. |
| Garlic Long Beans | Red chili SF058, 70 g | Optional: adjustable heat; garlic/oyster-sauce method still works without it. |
| Garlic Prawn | Garlic SF069, 12 g | Required: step 1 fries garlic; defining ingredient. |
| Garlic Spinach | Garlic SF069, 12 g | Required: step 1 fries garlic in butter. |
| Malay Chicken Soup | Soup spices SF134, 6 g | Required: step 2 explicitly adds the soup spice base. |
| Malaysian Chicken Curry | Curry powder SF133, 10 g | Required: step 1 fries the curry base. |
| Potato and Onion Stir-Fry | Turmeric SF135, 2 g | Required: step 2 explicitly fries turmeric with potato. |
| Sambal Eggplant | Dried shrimp SF052, 8 g | Required: step 1 fries the shrimp base. No fresh-prawn substitution. |
| Sardine Sambal | Tamarind SF139, 30 g | Required: step 3 simmers tamarind water into the sambal base. |
| Sardine Sambal | Lime SF098, 15 g | Optional: step 4 finishing acidity is adjustable; tamarind remains required. |
| Soy Sauce Eggs | Sugar SF118, 8 g | Optional: adjustable sweetness under the agreed seasoning exception. |
| Soy Sauce Mackerel | Sugar SF118, 6 g | Optional: adjustable sweetness. |
| Tomato Chicken | Turmeric SF135, 5 g | Required: step 1 specifies a turmeric marinade. |
| Tomato Tofu | Sugar SF118, 6 g | Optional: adjustable sweetness. |
| Turmeric Chicken | Turmeric SF135, 7 g | Required: step 1 coats chicken with turmeric; defining ingredient. |

Final catalogue: **222 required / 45 optional / 267 total**. Of the 145
pre-release optional rows, 100 become required and 45 stay optional. The
five retained legacy seasonings keep their existing reference amounts; their
optional flags ensure they do not block recipe readiness. Migration
`h4b5c6d7e8f9` also links all 100 promoted ingredients to their reviewed
cooking steps; a small migration journal records inserted links so rollback
preserves pre-existing links. Cooking instructions and their order do not change.
The migrations have exact rollback checks; meal types, component pairing and optimizer
eligibility remain unchanged. No UI layout or style changes are introduced.
