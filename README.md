# WiseBasket

WiseBasket is a budget-first household food planning system that helps B40
households in Malaysia build practical weekly food baskets within a hard food
budget, priced against real PriceCatcher grocery data.

Branch mapping: `develop` deploys to the UAT environment, `main` deploys to
PROD. All changes land on `develop` first and are merged to `main` after UAT
verification.

## Repository Structure

- `apps/mobile` - React Native / Expo user app (the primary client).
- `services/api` - FastAPI backend: auth, food catalogue, plan generation,
  store comparison, nearby prices, location search.
- `services/worker` - Celery worker + beat: daily PriceCatcher price refresh
  (07:30 Asia/Kuala_Lumpur), ON CONFLICT idempotent.
- `services/inference` - PaddleOCR receipt recognition and deterministic row parsing.
- `packages/optimizer` - OR-Tools CP-SAT solver: budget-constrained weekly
  planning with consumption budgets, purchase floors and whole-pack realism.
- `packages/food_data` - food mapping and data utilities.
- `data` / `migrations` / `scripts` - curated data, Alembic migrations,
  one-shot data-fix and seed scripts.
- `tests` - backend, optimizer, recipe and receipt regression tests.
- `docs` - architecture, product and deployment documentation.

## Current Capabilities (Iteration 2)

- Account registration / login with profile hydration (no re-typing between
  devices).
- Planning inputs: weekly budget, household size, meals-at-home, location
  (GPS fix or manual area), dietary restrictions (hard exclusions +
  gluten/custom text filters), usual-basket ticks.
- Deterministic, explainable weekly planning (OR-Tools CP-SAT):
  - Whole-pack purchasing; fresh meat/seafood by weight (25 g steps) with a
    1000 g / 1000 ml minimum purchase total per line; eggs and small
    seasonings keep their single-unit floor.
  - Per-person purchase floors and category consumption budgets, so a
    household never sees "1 apple for 4 people".
  - Hard dietary exclusions (CC1: excluded foods never enter the model).
- Opt-in shopping-list journey: tick the usual basket -> the plan is solved
  **within the selected set only** -> review the basket, accept
  worth-considering recommendations or add foods manually -> confirm ->
  price check. The review basket never gains or loses foods on a quantity
  re-solve; "Confirm & check prices" always re-solves the final list first.
- Worth-considering recommender: the LLM only picks `{food_id, angle}`
  (recipe pairing / nutrient gap / health upgrade) in JSON mode at
  temperature 0; every user-visible word comes from a curated bilingual tag
  table (no free-text LLM output). Recommendations lead with meal mains
  (fish/meat/poultry/eggs) and are stabilised by an in-process cache, so
  they do not flicker between re-solves. Without an API key a deterministic
  rule path produces the same-shaped list (feature never goes dark).
- Price intelligence: daily PriceCatcher refresh, per-district price
  resolution, nearby-store comparison with missing-item options, and a
  whole-basket price guide (store quotes plus plan estimates for unquoted
  items).
- Pantry presence can be saved without a quantity. Recipe badges count all
  listed ingredients; availability and quantity sufficiency are separate.
- Receipt review supports PaddleOCR, optional full-text LLM interpretation,
  label parsing and RapidFuzz matching and user-confirmed catalogue food links.
- Plan explanations are template-rendered and traceable to solver numbers.
  Optional LLM use also includes receipt interpretation and constrained substitutions.

See [Iteration 2 implementation notes](docs/iteration-2.md) for current behaviour,
deployment dependencies, validation evidence and known limitations.

## Local Development

Prerequisites: Python 3.12+, Node 20+, Docker (for PostgreSQL).

```bash
pip install -r requirements.txt
# start PostgreSQL, e.g.:
docker compose up -d postgres
export DATABASE_URL='postgresql+asyncpg://wisebasket:wisebasket@localhost:5432/wisebasket'
alembic -c config/alembic.ini upgrade head
uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000
```

API:
- `http://localhost:8000`
- `http://localhost:8000/docs`
- `http://localhost:8000/health`

Start the mobile app:

```bash
cd apps/mobile
npm install
npx expo start
```

For physical-device testing, set `EXPO_PUBLIC_API_BASE_URL` in
`apps/mobile/.env` to the computer LAN URL, for example
`http://192.168.1.10:8000` (Android emulator: `http://10.0.2.2:8000`), plus
`EXPO_PUBLIC_ASSET_BASE_URL` for the R2 food images.

## Testing

Backend (needs the Docker PostgreSQL above with migrations applied):

```bash
pytest -c config/pytest.ini -q
```

The CI-equivalent bar is a **fresh database with migrations only** (no seed
data): the SEED fixture worlds only appear there, so always re-check CI
failures against a clean database before changing code.

Mobile:

```bash
cd apps/mobile
node --test src/screens/*.test.mjs   # screen/behaviour tests
npx tsc --noEmit                     # type check
```

## Deployment

Railway (IaC; configuration lives in the dashboard / local `.railway/`,
which is git-ignored):

- `develop` branch -> UAT project, `main` branch -> PROD project.
- Services per project: API (Dockerfile `services/api/Dockerfile`), worker
  (`services/worker/Dockerfile`, Celery beat + worker), Postgres, Redis.
- **Migrations do not run automatically**: after deploying a branch that
  adds a migration, run `alembic upgrade head` against that environment's
  database.
- The worker refreshes prices daily at 07:30 Asia/Kuala_Lumpur; progress is
  tracked in the `price_update_state` table (month + content SHA).

## Documentation

Start with `docs/README.md` for the full documentation map: system overview,
mobile/backend/database architecture, API contracts, local setup,
deployment, testing, security and release readiness. The optimizer change
log (Chinese) with the full PR ledger and solver tuning cheat-sheet lives in
the team workspace at `git/documents/I1_优化器开发文档.md` (kept outside
this repo).
