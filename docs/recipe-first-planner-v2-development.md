# Recipe-first V2 development

## Database-free foundations

V1 was retired on 21 September 2026. The optimizer package no longer exposes
its basket-first `optimize` entry point and `POST /api/v1/plans` returns HTTP
410 with `PLANNER_V1_RETIRED`. V2 is being rebuilt from scratch without a
planner LLM dependency.

The pure calculation contracts cover recipe scaling, confirmed pantry
conservation, shortages, edible yields, integer purchase units, surplus, exact
cost, and two-decimal kg display. Decimal kg retain small ingredient
quantities. Positive quantities below 0.01 kg display as `<0.01 kg`.

Recipe and pantry quantities use raw edible kg. Purchase quantities use bought
weight. Adapters must normalize pantry records and establish the recipe
quantity basis before database records are connected. Only confirmed pantry
quantities reduce purchases. Unknown and estimated stock remain visible but do
not reduce the shopping list.

The provisional child recipe factor is 0.5 and explicitly configurable. This
is a portion assumption, not an RNI-derived standard. Purchased edible surplus
is excluded from recipe allocations, and over-budget evaluations never trim
portions.

The reviewed recipe domain fails closed on draft or disabled recipes,
non-meals, unsupported quantity bases, missing core roles, optional cooking
essentials, incomplete structured steps, and excluded foods. Substitutions are
directional, versioned, reviewed, role-compatible, and optionally scoped to a
recipe. Defining a substitution does not yet make it a solver decision.

The bounded CP-SAT selector uses whole recipe occurrences and purchase units.
It maximizes complete meals up to the requested target, then applies an
optional capped linear nutrition score, and finally minimizes exact purchase
cost. Recipe repetition limits, shared confirmed pantry stock, edible yield,
pack sizes, and the unrounded budget are model constraints. An infeasible full
target returns the maximum supported whole meals and an explicit shortfall.

Nutrition references are approximate planning thresholds: adult 2,000 kcal,
60 g protein and 1,000 mg calcium per day; child 1,600 kcal, 30 g protein and
1,000 mg calcium per day. They scale by household members and planned meal
occasions separately from the child recipe portion factor. Coverage rewards
are linear and capped at 100%, so extra nutrients cannot create unlimited
reward. Missing nutrition is disclosed and does not make a complete recipe
ineligible. These figures are not medical targets or intake ceilings.

## Test command

From the repository root:

```powershell
python -m pytest packages/optimizer/tests_v2 -q --confcutdir=packages/optimizer/tests_v2
```

These tests live outside the database integration suite, whose autouse
fixtures deliberately require local PostgreSQL and must never target UAT. The
ten-meal cost mimic uses synthetic recipe fixtures with frozen national UAT
prices observed on 14–15 September 2026. Its corrected RM74.93 total uses 0.90
kg purchased carrots rather than the earlier 0.95 kg estimate. It is not an
approved catalogue plan or a current store quote.

## Completed controlled milestones

1. Exact recipe scaling, pantry allocation, shortage, pack, yield, surplus,
   cost, budget, and display calculations.
2. Reviewed recipe completeness and curated substitution contracts.
3. Bounded recipe and purchase variables, exact meal target, maximum-meal
   shortfall, stock conservation, strict exact budget, and minimum cost.
4. Household nutrition references and capped linear nutrition scoring.
5. A deterministic synthetic 1-adult, 2-child, RM150, 10-meal scenario.
6. Staged pantry use, familiar-food preference, purchase surplus, ingredient
   reuse, and recipe variety objectives. Meal coverage and the exact budget
   remain higher priority than all quality preferences.
7. Approved substitutions as whole-recipe occurrence variants. Original and
   substituted occurrences share one recipe repetition cap, quantities use the
   reviewed ratio, and every applied replacement remains traceable. The
   original is retained when a substitution does not improve the plan.
8. Shortfall diagnostics and a typed API outcome contract. Budget shortfalls
   return `INSUFFICIENT_BUDGET` with the minimum additional amount. Structural
   failures return stable error codes without presenting extra money as a fix.
9. A database-free V2 application service with typed request and full plan
   response models. Pantry defaults to an empty list. Unknown and estimated
   entries remain visible inputs but only confirmed quantities reduce shopping.
   Food preferences never imply pantry ownership.
10. Optional dietary-pattern and allergen safety filtering. Empty selections
    preserve normal planning without requiring safety metadata. When a rule is
    selected, unknown safety data fails closed and is disclosed through
    `MISSING_SAFETY_METADATA`; substitutions use the same exclusions.
11. End-to-end controlled family personas covering an empty pantry, confirmed
    pantry deductions, ten complete meals, deterministic preferences, missing
    price IDs, edible yield, package counts, visible purchase surplus, approved
    substitution traceability, exact line-to-total reconciliation, and a
    lower-budget shortfall without fractional meals.
12. A dependency-injected FastAPI `POST /api/v2/plans` router tested with an
    in-memory catalogue provider. Clients cannot submit catalogue recipes or
    prices. Request validation remains HTTP 422, planning shortfalls remain
    typed HTTP 200 outcomes, and provider outages return a stable HTTP 503 code.
13. A catalogue acceptance gate before optimization. Duplicate recipe, purchase,
    nutrition, safety, and substitution identities fail closed, as do noneligible
    recipes and broken substitution references. Invalid provider data returns
   `PLANNER_V2_CATALOG_INVALID`; an empty valid catalogue remains a typed
   `NO_ELIGIBLE_RECIPE` planning outcome.
14. User-selection anchoring. A non-empty `selected_food_ids` list limits the
    solve to recipes connected to at least one endorsed food. The mobile client
    keeps those foods in Week plan, treats Skip as a hard exclusion, and sends
    the displayed amount of Have foods as confirmed pantry stock.
15. Recipe opportunity bundles. Worth considering evaluates every connected
    approved recipe, returns only complete bundles whose missing ingredients
    have trusted purchase options and fit the stated budget, and ranks reusable
    ingredients ahead of single-recipe ingredients. Reuse counts include other
    safe approved recipes even when their complete bundle cannot yet be priced.
    The mobile adapter deduplicates ingredients across bundles and never repeats
    a Week plan food.

## Next controlled milestones

1. Build and audit the read-only database catalogue adapter without schema
   changes or writes.
2. Mount the live `/api/v2/plans` route after that provider passes controlled
   mapping and UAT read-only audit tests.
   do not accept client-supplied recipes or prices.
3. Only after these boundaries are stable: read-only UAT adapters and audits,
   then local-database persistence tests and schema changes. UAT must never be
   used by destructive test fixtures.
