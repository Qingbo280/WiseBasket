# Local Setup

This document explains how to run WiseBasket locally. It is intended for developers and testers.

It assumes Python, Node.js, npm and a reachable PostgreSQL database are available. For phone testing, the phone and computer must be on the same network.

## 1. Create Backend Environment File

From the repository root:

```env
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://wisebasket:wisebasket@localhost:5432/wisebasket
CORS_ORIGINS=http://localhost:3000,http://localhost:8081
JWT_SECRET=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=30
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
LLM_ENABLED=true
LLM_TIMEOUT_S=30
GEOAPIFY_API_KEY=<geoapify-api-key>
GEOAPIFY_BASE_URL=https://api.geoapify.com/v1/geocode/autocomplete
GEOAPIFY_TIMEOUT_S=5
```

Save this as `.env`. Do not commit `.env`.

## 2. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

## 3. Run Database Migrations

```bash
alembic -c config/alembic.ini upgrade head
```

## 4. Load Local Reference Prices

For local recipe-planner testing, load the governed retailer reference prices
for approved-recipe foods that are not covered by PriceCatcher:

```bash
python scripts/load_optimizer_reference_prices_to_local.py \
  --database-url postgresql://wisebasket:wisebasket@localhost:5432/wisebasket
```

The loader is local-only and idempotent. These rows use the
`REFERENCE_ESTIMATE_2026-09` dataset label and remain marked as estimated in
API and mobile price results.

## 5. Start Backend API

```bash
uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000
```

Check the API after startup:

```text
http://localhost:8000/health
http://localhost:8000/docs
```

## 6. Start Mobile App

```bash
cd apps/mobile
npm ci
npx expo start
```

## 7. Configure Mobile API URL

Create:

```text
apps/mobile/.env
```

For a physical phone:

```env
EXPO_PUBLIC_API_BASE_URL=http://<PC_LAN_IP>:8000
```

For public Railway backend:

```env
EXPO_PUBLIC_API_BASE_URL=https://your-wisebasket-api.up.railway.app
```

## 8. Run Tests

For receipt OCR, start the inference service using its own requirements and configure `INFERENCE_URL` in the API. Start Redis and the Celery worker for queued processing, or leave the broker unconfigured to exercise inline extraction. LLM interpretation requires the existing server-side provider credentials and `LLM_ENABLED=true`; it does not read images directly. See [Iteration 2 runtime and validation](../iteration-2.md).

Use a dedicated local/CI database for the backend suite below. It runs destructive fixtures and must not target a shared Railway database. Mobile hosted images can additionally use `EXPO_PUBLIC_ASSET_BASE_URL`.

Backend tests:

```bash
pytest -c config/pytest.ini -q
```

Mobile type check:

```bash
cd apps/mobile
npm run typecheck
```

## Troubleshooting

| Problem | Check |
| --- | --- |
| Mobile cannot connect to API | Confirm `EXPO_PUBLIC_API_BASE_URL` uses the computer LAN IP, not `localhost`, when testing on a physical phone. |
| API cannot connect to database | Confirm PostgreSQL is running and `DATABASE_URL` points to the correct host, port, user and database. |
| JWT error outside local development | Confirm `JWT_SECRET` is not `change-me`. |
| Plan request times out | Plan generation may take longer when optional explanation/meal text is enabled; use the mobile planner timeout path. |
