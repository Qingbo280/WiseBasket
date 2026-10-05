# WiseBasket Iteration 2 Data Dictionary

## Iteration 2 additions

The original planning and canonical-data definitions below remain applicable. Current pantry, recipe and receipt models are defined in `services/api/app/db.py`; see [Iteration 2](../iteration-2.md) for workflow meaning and limitations.

| Entity/field | Meaning |
| --- | --- |
| `pantry_item` | Household canonical food presence with `AVAILABLE`/`REMOVED` status, manual/receipt source and optional quantity/unit. |
| `recipe_catalog` | Active recipes with name, description and optional base servings. |
| `recipe_catalog_ingredient` | Ordered canonical ingredient links, required flag and optional base grams. |
| `recipe_cooking_step` | Ordered recipe instructions. |
| `receipt` | Household upload lifecycle, expiring source image and extraction status. |
| `receipt_line` | Ordered review drafts, printed/expanded names, proposed food, candidates, price and amount fields. |
| API `ingredient_count` | Calculated number of all listed recipe ingredients; not a stored recipe column. |
| LLM `source_row_ids` | One-based raw transcript row IDs used to ground full-text extraction; not persisted receipt UUID IDs or a current database column. |

Presence counts include optional recipe ingredients for badges. Required-match counts and household-scaled quantity sufficiency remain separate. Unknown pantry quantities do not prove enough stock.

> Draft team data contract for WiseBasket Epics 1–4. Update column names/types after the final Codex migration is approved.

## 1. Purpose

This document explains:
- what each table means,
- which team owns it,
- how data moves through WiseBasket,
- which data is safe for the optimizer,
- and which rules must never be bypassed.

## 2. End-to-end data flow

```text
PriceCatcher / MyFCD / RNI / reviewed mappings
                    ↓
              Data / ETL layer
                    ↓
          Trusted PostgreSQL tables
                    ↓
          Optimizer-ready data view
                    ↓
               FastAPI backend
          ┌─────────┼──────────┐
          ↓         ↓          ↓
       OR-Tools  Store ranker  Admin APIs
          ↓         ↓
      Food plan + one recommended store
                    ↓
                 Expo app
```

**Core rule:** raw/review data is not automatically optimizer-ready data.

## 3. Team ownership

| Team | Main responsibility |
|---|---|
| BIS | User inputs, business rules, acceptance criteria, user-facing behavior |
| Data | Canonical food identity, mappings, prices, nutrition, units, provenance, ETL, data quality |
| AI | Optimizer input/output contract, OR-Tools logic, hard constraints, evaluation |
| Backend | FastAPI, auth, persistence, planning workflow, store-ranking workflow |
| Mobile | Sends user inputs and displays API results |
| Admin | Reviews mappings/data quality, manages catalogue, inspects plans and stores |

## 4. Authentication

### `app_user`
Single login identity for mobile users and admins.

Key fields:
- `user_id`: UUID
- `email`: login email
- `password_hash`: Argon2id hash only
- `role`: `USER` / `ADMIN`
- `status`: `ACTIVE` / `DISABLED` / `LOCKED`
- `email_verified`
- `created_at`, `updated_at`

Rules:
- never store plaintext passwords,
- never return password hashes to clients,
- enforce admin access in FastAPI.

### `user_profile`
Optional normal-user profile information.

### `admin_profile`
Admin-specific metadata such as `ADMIN` / `SUPER_ADMIN`.

### `auth_session`
Tracks refresh-token sessions.

Typical fields:
- `session_id`
- `user_id`
- `refresh_token_hash`
- `client_type`: `MOBILE` / `ADMIN_WEB`
- `device_name`
- `expires_at`
- `revoked_at`
- `created_at`

Rule: store only the hash of the refresh token.

## 5. Epic 1 — Household & planning constraints

### `household`
Persistent household record owned by a user.

Typical fields:
- `household_id`
- `user_id`
- `household_name`
- `adults`
- `children`
- timestamps

Derived value:
`household_size = adults + children`

Rules:
- adults >= 0
- children >= 0
- total household size > 0

### `planning_request`
One request to generate a food plan.

Typical fields:
- `planning_request_id`
- `household_id`
- `available_budget_rm`
- `planning_days`
- `created_at`

Rules:
- budget > 0
- planning days > 0
- budget is a hard constraint.

### `planning_location`
Location used for one planning request.

Fields:
- `planning_request_id`
- `latitude`
- `longitude`
- `location_source`: `GPS` / `MANUAL`
- `selected_state`
- `selected_district`

Rules:
- latitude -90..90
- longitude -180..180
- store only the precision needed.

### `hard_exclusion`
Master list of supported hard constraints.

Examples:
- `PEANUTS`
- `SHELLFISH`
- `EGGS`
- `MILK`
- `VEGETARIAN`
- `NO_PORK`

These are not preferences.

### `planning_request_exclusion`
Links a planning request to active exclusions.

Primary key:
`planning_request_id + exclusion_code`

### `hard_exclusion_food`
Maps an exclusion to blocked `canonical_food_id` values.

Example:

```text
NO_PORK
  ↓
FOOD_PORK_BELLY
FOOD_PORK_LOIN
FOOD_MINCED_PORK
```

Do not rely on string matching like `if "pork" in name`.

## 6. Epic 2 — Trusted food, nutrition and price data

### `canonical_food`
WiseBasket's master food identity.

Examples:
- `FOOD_0001` → Rice
- `FOOD_0002` → Chicken
- `FOOD_0003` → Tofu

Typical fields:
- `canonical_food_id`
- `canonical_name`
- `canonical_name_ms`
- `category`
- `food_form`
- `status`: `ACTIVE` / `BLOCKED` / `RETIRED`
- timestamps

All optimizer, nutrition, price, exclusion and plan records should eventually reference `canonical_food_id`.

### `food_alias`
Alternative names for the same canonical food.

Useful for:
- source matching,
- search,
- future OCR/voice,
- admin review.

### `source_food_mapping`
Maps PriceCatcher/MyFCD/source records to canonical foods.

Typical fields:
- source system/version/id/name
- canonical food ID
- mapping status
- verification status
- review status
- reviewer/date/evidence

Mapping statuses:
- `CANDIDATE`
- `EXACT`
- `ACCEPTED_EQUIVALENT`
- `NEEDS_CONVERSION`
- `AMBIGUOUS`
- `UNMAPPED`
- `EXCLUDED`

Verification statuses:
- `NOT_VERIFIED`
- `VERIFIED`
- `REJECTED`

Review statuses:
- `PENDING`
- `APPROVED`
- `REJECTED`

An approved mapping must carry reviewer attribution.

### `food_nutrition`
Trusted nutrition profiles for canonical foods.

Typical fields:
- `canonical_food_id`
- source dataset/version/record
- `basis_g`
- energy, protein, fat, carbohydrate, fibre
- fibre basis
- iron, calcium, vitamin A, vitamin C
- quality status
- `is_current`
- source URL/retrieval timestamp

Critical rule:

```text
Unknown != 0
```

Missing nutrient values stay `NULL`.

### `food_asset`
Metadata for images stored in R2/S3-compatible object storage.

Typical fields:
- `food_asset_id`
- `canonical_food_id`
- `asset_type`: `IMAGE` / `THUMBNAIL`
- `object_key`
- `alt_text`
- `is_primary`
- `created_at`

Example object key:
`foods/FOOD_0001/rice.webp`

Actual image bytes live in object storage, not PostgreSQL.

### `location`
Master record for stores/premises.

Typical fields:
- `location_id`
- `source_premise_code`
- `location_name`
- `premise_type`
- `state`
- `district`
- `address`
- `latitude`
- `longitude`
- `active`
- timestamps

Used by price observations and Epic 4.

### `unit_conversion`
Converts retail units into optimizer-usable quantities.

Conversion types:
- `PURCHASE_MASS`
- `EDIBLE_YIELD`

Typical fields:
- conversion ID
- canonical food / source item
- from/to unit
- factor
- evidence
- status
- version
- `production_eligible` boolean

Rules:
- production-eligible conversion needs a valid factor,
- edible yield must be >0 and <=1.

### `etl_run`
One data pipeline/import run.

Used for:
- provenance,
- reproducibility,
- admin monitoring,
- debugging.

Typical fields:
- pipeline version
- source system/vintage
- start/end time
- status
- rows in/out/blocked

### `food_price_observation`
One observed retail price at one premise on one date.

Typical fields:
- canonical food
- source item
- source premise
- location
- observed date
- retail price
- original unit
- purchase mass
- normalized purchase prices
- edible yield
- edible price per 100g
- source dataset version
- ETL run
- quality status

Rule: preserve history. Do not collapse everything into one permanent “current price”.

### `rni_reference`
Trusted nutrient reference records.

Iteration 2 should use documented simplified assumptions instead of pretending the app has more demographic detail than it actually collects.

### `data_quality_issue`
Records pipeline/data problems.

Severity:
- `INFO`
- `WARN`
- `BLOCK`

This should drive the admin Data Quality screen.

## 7. Epic 3 — Optimisation

### `meal_template`
Simple structured meal definitions so OR-Tools does not produce arbitrary unrealistic food quantities.

Examples:
- Chicken + Rice + Vegetable
- Tofu + Rice + Vegetable

### `meal_template_ingredient`
Links a meal template to canonical foods and grams per serving.

### `generated_plan`
Stores one optimizer result.

Typical fields:
- `plan_id`
- `planning_request_id`
- `optimizer_version`
- `generation_method`
- `status`: `FEASIBLE` / `TIGHT` / `INFEASIBLE`
- estimated total cost
- remaining budget
- solver runtime
- selected store option
- created time

Persisting plans enables debugging, user history and academic evaluation.

### `generated_plan_item`
Foods selected by one generated plan.

Typical fields:
- plan item ID
- plan ID
- canonical food ID
- quantity
- unit
- estimated cost

## 8. Epic 4 — One-store recommendation

### `plan_store_option`
Stores each store evaluated for a generated basket.

Typical fields:
- plan ID
- location ID
- distance
- basket cost
- items available/missing
- coverage ratio
- ranking
- recommendation type
- selected flag

Recommendation types:
- `NEAREST`
- `CHEAPEST`
- `BEST_VALUE`

Iteration 2 evaluates multiple stores but recommends **one store only**.

### `plan_store_item`
Explains how a store's basket cost was calculated.

Typical fields:
- store option
- canonical food
- price observation used
- estimated item cost
- availability

Rule: if price is missing, mark it unavailable. Never invent the price.

## 9. Derived views

### `v_latest_food_price`
Latest usable `PASS` price per:
`canonical_food_id + location_id`

Historical observations remain unchanged.

Consumers:
- Epic 4 ranker
- admin price viewer
- optimizer candidate builder

### `v_optimizer_food_candidate`
Main clean Data → AI/backend contract.

Expected fields include:
- canonical food ID/name/category
- normalized usable price
- nutrition
- location
- observed date
- quality states

Typical eligibility:

```text
canonical food ACTIVE
AND mapping acceptable
AND nutrition not BLOCK
AND price PASS
AND required unit conversion usable
AND normalized usable price exists
```

The AI team should consume this view/service contract instead of raw source tables.

## 10. How each team should use the data

### Mobile
Use FastAPI only.

Do not:
- connect directly to PostgreSQL,
- read PriceCatcher CSVs,
- calculate authoritative prices locally.

### AI
Main input:
`v_optimizer_food_candidate` or an equivalent backend DTO.

Do not:
- guess prices,
- guess nutrition,
- resolve raw source names,
- bypass hard exclusions.

### Data
Own:
- canonical identity,
- mappings,
- nutrition,
- prices,
- units,
- provenance,
- ETL,
- quality state.

### BIS
Own the meaning of:
- budget,
- household composition,
- planning days,
- hard exclusions,
- user location flow,
- plan status behavior,
- store recommendation behavior.

### Backend
Owns:
- validation,
- authentication,
- authorization,
- persistence,
- candidate retrieval,
- exclusion resolution,
- OR-Tools invocation,
- store ranking,
- API contracts.

### Admin
Admin data mapping:

| Dashboard module | Main tables |
|---|---|
| Food Catalogue | `canonical_food`, `food_asset`, `food_alias` |
| Mapping Review | `source_food_mapping` |
| Nutrition | `food_nutrition` |
| Price Explorer | `food_price_observation`, `location` |
| Unit Review | `unit_conversion` |
| Store Viewer | `location` |
| ETL Monitor | `etl_run` |
| Data Quality | `data_quality_issue` |
| Planner Test Console | planning + optimizer service |
| Generated Plans | `planning_request`, `generated_plan`, `generated_plan_item` |
| Store Debug | `plan_store_option`, `plan_store_item` |

## 11. Important identifiers

| ID | Represents |
|---|---|
| `user_id` | Authenticated human |
| `household_id` | User household |
| `planning_request_id` | One request to generate a plan |
| `canonical_food_id` | WiseBasket food identity |
| `source_food_id` / `source_item_code` | External source record |
| `location_id` | WiseBasket store/premise |
| `source_premise_code` | External store ID |
| `plan_id` | Generated optimizer result |
| `price_observation_id` | One observed price |
| `etl_run_id` | One ETL execution |

## 12. Non-negotiable data rules

1. Unknown values stay `NULL`; unknown is not zero.
2. Prices must retain source, premise, date and dataset provenance.
3. Hard exclusions resolve to blocked canonical IDs and are enforced before OR-Tools.
4. Images are stored in object storage; PostgreSQL stores the object key.
5. A row existing in PostgreSQL does not automatically make it optimizer-eligible.
6. Preserve price history; use views/services to choose latest values.
7. Iteration 2 recommends one practical store, not a multi-store split.
8. No LLM may invent price, nutrition, constraints or feasibility.

## 13. Example planning flow

```text
1. Authenticate user
2. Validate household ownership
3. Save planning request
4. Save planning location
5. Save hard exclusions
6. Resolve exclusions to blocked canonical food IDs
7. Query optimizer-ready candidates
8. Remove blocked foods
9. Run OR-Tools
10. Save generated plan/items
11. Find nearby stores
12. Load latest PASS prices
13. Calculate basket cost and coverage
14. Rank stores
15. Select ONE store
16. Save store-option/item results
17. Return plan to Expo
```

## 14. Before a food reaches OR-Tools

- [ ] Canonical food exists
- [ ] Food is ACTIVE
- [ ] Source mapping is acceptable
- [ ] Required nutrition is usable
- [ ] Required unit conversion is usable
- [ ] Edible yield is valid where needed
- [ ] A usable PASS price exists
- [ ] Price belongs to a known location
- [ ] Price date is available
- [ ] Food is not blocked by a hard exclusion

Only after these checks should the food become an optimizer candidate.

## 15. Maintenance

Update this dictionary whenever:
- migrations add/remove/rename fields,
- source systems change,
- eligibility rules change,
- exclusions change,
- store-ranking logic changes,
- later epics add pantry/OCR/preferences/AI.
