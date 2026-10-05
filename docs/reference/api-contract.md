# API Contract

This document summarises the WiseBasket Iteration 2 API contract. It is intended for mobile developers, backend developers and testers.

FastAPI also exposes generated OpenAPI documentation at:

```text
/docs
```

when the API is running.

## Base URL

| Environment | Base URL example |
| --- | --- |
| Local computer | `http://localhost:8000` |
| Local physical phone | `http://<PC_LAN_IP>:8000` |
| Railway public API | `https://your-wisebasket-api.up.railway.app` |

## Authentication

### Register

```http
POST /api/v1/auth/register
```

Request:

```json
{
  "email": "user@example.com",
  "password": "password123",
  "client_type": "MOBILE",
  "device_name": "Pixel test phone"
}
```

Response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in_seconds": 900,
  "user": {
    "user_id": "...",
    "email": "user@example.com",
    "role": "USER",
    "status": "ACTIVE",
    "email_verified": false
  }
}
```

### Login

```http
POST /api/v1/auth/login
```

Request:

```json
{
  "email": "user@example.com",
  "password": "password123",
  "client_type": "MOBILE",
  "device_name": "Pixel test phone"
}
```

### Refresh

```http
POST /api/v1/auth/refresh
```

Request:

```json
{
  "refresh_token": "..."
}
```

The backend rotates refresh tokens. Mobile clients must save the new refresh token before retrying failed authenticated requests.

### Current User

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

## Food Catalogue

```http
GET /api/v1/foods
Authorization: Bearer <access_token>
```

Returns optimizer-eligible foods from the current database-backed candidate set.

Key fields:

| Field | Meaning |
| --- | --- |
| `food_id` | Stable canonical food ID used by the planner. |
| `name` | English display name. |
| `name_ms` | Malay display name if available. |
| `category` | Food category used for grouping and plan interpretation. |
| `exclusion_codes` | Hard-exclusion codes linked to the food. |
| `price_rm_per_100g` | Current usable price basis for planning. |
| `nutrients` | Nutrient values used for summaries and constraints. |

## Supported Locations

```http
GET /api/v1/locations/supported
```

Returns active state/district options from the backend `location` table for manual shopping-area selection.

Example response:

```json
[
  {
    "state": "Selangor",
    "districts": ["Klang", "Petaling"]
  }
]
```

## Profile

```http
GET /api/v1/profile
PUT /api/v1/profile
Authorization: Bearer <access_token>
```

The profile stores a frontend-owned planning snapshot, such as budget, household size, restrictions, location and usual basket.

PUT request:

```json
{
  "profile": {
    "weeklyBudget": 120,
    "adults": 2,
    "children": 2,
    "restrictions": ["no-pork"],
    "state": "Selangor",
    "district": "Petaling"
  }
}
```

## Plan Generation

```http
POST /api/v1/plans
```

The basket-first V1 planner is retired. Every payload receives HTTP `410 Gone`
with code `PLANNER_V1_RETIRED`; no legacy or persisted payload shape can reach
optimizer code.

The active recipe-first contract is `POST /api/v2/plans`. `selected_food_ids`
anchors the solve to recipes containing at least one food the user endorsed.
`pantry` supplies confirmed quantities, while `excluded_food_ids` removes Skip
choices. The response allocations let the client keep endorsed foods in Week
plan. `recipe_opportunities` groups the priced missing ingredients for each
connected approved recipe and reports package quantity, estimated bundle cost,
additional meal capacity, and recipe reuse count. The client flattens these
bundles into Worth considering while keeping their recipe reasons and removing
anything already in Week plan.
The full development contract is documented in
`docs/recipe-first-planner-v2-development.md`.

## Households

```http
POST /api/v1/households
GET /api/v1/households
Authorization: Bearer <access_token>
```

Household records store adults, children and owner user context for persisted planning.

## Iteration 2 Pantry, Recipes and Receipts

These routes require bearer authentication and household ownership. Prefix household routes with `/api/v1/households/{household_id}`.

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET / POST | `/pantry-items` | List available pantry records or add canonical food presence. |
| PATCH / DELETE | `/pantry-items/{pantry_item_id}` | Update or remove a pantry record. |
| POST | `/pantry-confirmations` | Confirm the current pantry snapshot. |
| GET | `/recipe-suggestions` | Browse active recipes ranked against current pantry. |
| GET | `/recipes/{recipe_id}` | Ingredients, instructions, scaled amounts and substitutions. |
| POST | `/receipts` | Upload receipt image as multipart form data. |
| GET | `/receipts/{receipt_id}` | Poll extraction status and read draft lines. |
| POST | `/receipts/{receipt_id}/confirm` | Confirm existing and manually added item rows. |

Pantry creation accepts `canonical_food_id` without quantity. Recipe browsing does not require a first pantry confirmation. Quantity sufficiency is separate from presence.

Recipe responses include `available_ingredients`, `missing_required_ingredients`, `required_match_count`, `required_ingredient_count` and the new `ingredient_count`. Badges use available list length divided by total ingredient count, including optional ingredients. Required-match fields remain available for ranking. Older responses may omit the total; clients show available count without inventing a denominator.

Receipt status is `PENDING`, `PROCESSING`, `DONE` or `FAILED`. Drafts retain UUID `line_id`, `display_order`, raw label, amount fields, proposed catalogue food and candidates. Raw labels are hidden on the review page. Confirmation uses `lines` for existing IDs and `added_lines` for manual purchases; food replacement updates its existing line.

The internal inference endpoint `/receipt/extract` accepts `image_base64` and returns `lines`, `raw_text` and an optional error. The full-text LLM extractor uses `source_row_ids` to ground purchase drafts in transcript rows, distinct from persisted UUID line IDs.

## Status Code Reference

| Code | Meaning |
| --- | --- |
| `200` | Request succeeded. |
| `401` | Missing or invalid authentication. |
| `403` | Authenticated user does not have permission. |
| `409` | Registration conflict, such as duplicate email. |
| `422` | Validation or planning-data problem. |
| `500` | Unexpected backend error. |

## Contract Rules

- The mobile app must not send negative budgets, impossible household sizes or invalid latitude/longitude.
- The backend validates all request models before service logic runs.
- Budget and restriction handling must be deterministic and testable.
- The API URL must be supplied by environment configuration in the mobile app.
