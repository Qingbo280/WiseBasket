# Recipe ingredient reuse audit (2026-09-29)

Scope: all 35 reviewed recipes (267 ingredient rows), the authoritative
canonical-food ledger, current oil equivalence and the Epic 5 substitution
rules. The approved first batch is implemented in
`services/api/app/services/recipe_ingredient_reuse.py`; the remaining rows
are audit candidates, not approved automatic matches. A shopping
recommendation's `INTRODUCTION_FAMILY_BY_FOOD_ID`
only avoids redundant purchases; it is **not** evidence that two foods are
culinarily or quantitatively interchangeable.

## Confirmed mismatch

Malaysian Chicken Curry requires `SF014` chicken thigh. `SF006` whole chicken,
`SF013` whole leg, `SF015` drumstick, `SF016` wing and `SF017` breast are separate pantry IDs.
Before this batch, suggestions and detail endpoints checked exact IDs, so a
household with whole chicken could be shown as missing chicken. The existing
`whole-chicken-to-chicken-breast` substitution rule is directional and only
produces a detail-page suggestion; it does not change matching, card counts,
ranking, or quantity sufficiency.

## Candidates across the 35 recipes

| Recipe ingredient and affected recipes | Candidate pantry foods | Decision |
| --- | --- | --- |
| Chicken: `SF006` whole (3 recipes), `SF014` thigh (2 recipes) | `SF006`, `SF013` whole leg, `SF014`, `SF015` drumstick, `SF016` wing, `SF017` breast | Approved recipe-specific chicken-meat slot for soup, curry, soy-sauce, tomato, turmeric dishes. `SF007` live chicken is not an automatic equivalent. Wing's bone ratio makes its measured mass non-comparable. |
| `SF022` white prawn (3 recipes) | `SF036` tiger prawn | Same fresh prawn role by usable mass; `SF052` dried shrimp is not equivalent. |
| `SF024` Spanish mackerel (1 soy-sauce recipe) | `SF025` Indian mackerel | Plausible recipe-specific fish swap; cooking size and fish form need review before quantity sufficiency is asserted. |
| `SF035` red tilapia (1 recipe explicitly named red tilapia) | `SF049` black tilapia | Culinary substitute, but the card title would be inaccurate without a variation label. Do not silently mark this exact recipe complete yet. |
| `SF102` boxed coconut milk (2 curries) | `SF103` fresh coconut milk | Same culinary function; fat/water concentration differs. Presence may match; measured sufficiency needs a reviewed conversion or stays unknown. `SF104` grated coconut and `SF105` coconut do not qualify. |
| `SF110` rice (20 recipes) | `SF113` basmati rice | Both non-glutinous dry rice for a served-rice slot. `SF112` glutinous rice and `SF115` rice flour do not qualify. Do not count two rice SKUs as two ingredients. |
| `SF120` bottled cooking oil (33 recipes after optionality correction) | `SF121` corn oil, `SF123` packet cooking oil | Already handled in suggestion presence and quantity pooling; retain the existing one-slot, one-stock-pool behaviour. Butter is not in this group. |
| `SF098` lime (1 required sardine sambal; 1 optional spinach recipe) | `SF083` calamansi lime | Plausible finishing-acid swap; acidity differs. Review per recipe before auto-matching. |

## Recipe-specific variations, not blanket equivalence

- `SF055` cabbage versus `SF059` Chinese cabbage (six cabbage recipes): water
  content/texture differ. Could be offered for mixed vegetable or tofu-cabbage
  dishes after individual review, but should not silently satisfy the named
  Mamak cabbage dish.
- `SF062` spinach, `SF074` water spinach and `SF081` mustard greens: all leafy
  vegetables, but dish names and cooking behaviour differ. The existing
  water-spinach-to-spinach suggestion should not become a global family rule.
- `SF067` french beans, `SF084` long beans and `SF068` winged beans: different
  texture and recipe identity; review only for generic mixed-vegetable dishes.
- `SF018` chicken egg, `SF020` duck egg and `SF021` quail egg: possible in some
  omelettes but different size/flavour; no automatic 1:1 match. `SF019` salted
  egg is not equivalent to a raw cooking egg.
- `SF109` fresh yellow noodles, `SF108` fresh rice noodles, `SF159` dried rice
  vermicelli and `SF161` packet instant noodles have different hydration,
  mass basis and named dishes; do not silently merge them.
- `SF135` turmeric powder and `SF070` fresh turmeric require a reviewed
  potency conversion; no mass-for-mass match.
- `SF156` canned sardine and `SF157` canned mackerel make different named
  dishes; no automatic match.

## First-batch implementation contract

The first batch uses an explicit, directed **recipe + ingredient slot →
approved alternatives** table for chicken, fresh prawn, coconut milk and
served rice. Both suggestion and detail endpoints resolve the same slot. A
slot counts once even if several variants are in pantry; the additive API
`matched_alternatives` map reports which pantry SKU was used. Exact food
takes precedence. A substituted food with unknown quantity may satisfy
presence but must **not** establish sufficiency. Prawn and rice purchase
masses are comparable; chicken-cut and coconut-milk masses return `UNKNOWN`
without a validated yield/concentration conversion. Hard exclusions and
name-based restrictions filter substitute candidates before matching.

The existing detail-only substitution-suggestion rules remain a separate
legacy feature for now; a matched first-batch alternative is suppressed from
that suggestion list to avoid duplicate messaging. A later consolidation
should move all approved suggestions into the slot table, then review the
conditional fish, citrus and vegetable cases above.

The list and detail responses project a matched **real pantry SKU** into the
existing food ID/name/image fields. For example, curry's stored thigh slot
displays whole chicken when that is the approved stock match; with no chicken
stock it still displays the recipe's original thigh, so "Need it" does not
silently add a whole chicken. Stored recipe rows, matching counts, and pantry
records are unchanged. The original-to-actual IDs remain available in
`matched_alternatives`. Chicken-cut and coconut-milk substitutes have no
asserted gram equivalence; their display-facing quantity fields are null and
their sufficiency is `UNKNOWN`. No Recipe UI/UX code was changed. The existing
card shows at most two preview ingredients, so it cannot promise to show every
missing ingredient without a separately approved UI/UX change.

The existing ten-card ranking still prioritizes known sufficient amounts.
Within that limit, a reviewed main-protein substitute may pass the usual
three-recipes-per-protein diversity cap (up to five), so three exact whole-
chicken dishes do not automatically hide both thigh-based chicken dishes.
