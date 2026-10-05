# Railway Deployment

This document explains the production backend deployment approach for WiseBasket on Railway. It is intended for deployment owners and assessors reviewing system maintenance readiness.

It covers Iteration 2 API, database, inference and optional queued worker support. Actual deployment status must be verified separately.

## Services

| Railway service | Purpose |
| --- | --- |
| API service | Runs FastAPI through Uvicorn. |
| PostgreSQL | Stores users, planning requests, generated plans, food data, price data and location data. |
| Inference | PaddleOCR recognition and parser source rows. |
| Redis | Broker for queued receipt jobs when configured. |
| Worker | Celery receipt extraction and scheduled data work. |

## API Build Configuration

Configure the Railway API service to build:

```text
services/api/Dockerfile
```

Key settings:

| Setting | Meaning |
| --- | --- |
| `builder = "DOCKERFILE"` | Railway builds from the API Dockerfile. |
| `dockerfilePath = "services/api/Dockerfile"` | Uses the backend Dockerfile. |
| `startCommand` | Starts Uvicorn on Railway's assigned `PORT`. |
| `healthcheckPath = "/health"` | Railway checks the API health endpoint. |
| `watchPatterns` | Deploys when backend, shared package, requirement or Railway config files change. |

## Required Environment Variables

| Variable | Required in production | Notes |
| --- | --- | --- |
| `APP_ENV` | Yes | Use a non-development value such as `production`. |
| `DATABASE_URL` | Yes | Railway PostgreSQL connection string. |
| `JWT_SECRET` | Yes | Must be strong, at least 32 characters and must not be `change-me`. |
| `JWT_ALGORITHM` | Yes | Usually `HS256`. |
| `ACCESS_TOKEN_MINUTES` | Yes | Current default is `15`. |
| `REFRESH_TOKEN_DAYS` | Yes | Current default is `30`. |
| `CORS_ORIGINS` | Yes | Include allowed public origins only in production. UAT may explicitly include local Expo Web origins for browser QA; wildcard origins are always removed. |
| `DEEPSEEK_API_KEY` | Optional | Receipt interpretation only; planner V2 does not use an LLM. |
| `LLM_ENABLED` | Optional | Disabled/unavailable LLM execution retains deterministic fallbacks. |
| `INFERENCE_URL` | Required for receipt OCR | Reachable inference service URL in API and worker. |
| `REDIS_URL` | Required for queued receipts | Shared API/worker broker; absent broker uses inline API extraction. |
| `RECEIPT_REPROCESS_DONE_UPLOADS` | Optional, API upload policy | Defaults to `false` in every environment. Set an existing UAT `true` override to `false` to reuse completed analysis instead of invoking local redaction/OCR and the cloud parser again. Explicit `true` is only for QA model comparisons; production rejects it. Active identical uploads always coalesce. Fresh scans consume daily quota/cloud budget; cached reviews do not. Matching uses image bytes within the same household, not visually similar photos. |
| `RECEIPT_ALLOW_REPEAT_PURCHASES` | Optional, API confirmation policy | Defaults to `true` in UAT/staging only, otherwise `false`; explicit `true` is allowed only in UAT/staging/test/testing. In QA, re-uploading a confirmed image creates a new review with fresh line IDs from saved OCR/review rows (including prior corrections, excluding manual additions); no extraction or image retention is repeated. Pending/unconfirmed reviews are reused. Confirming this new review can add stock/spending again, while retrying the same confirmation stays idempotent. Set `false` to test production duplicate protection. Production still blocks repeat purchases. No schema migration. |
| `GEOAPIFY_API_KEY` | Required for location search | Server-side key for manual address autocomplete. |

## Deployment Steps

1. Create a Railway project.
2. Add a PostgreSQL service.
3. Create an API service connected to the GitHub repository.
4. Configure the service to use `services/api/Dockerfile` and verify its build/start settings.
5. Add all required environment variables.
6. Deploy the API service.
7. Verify:

```text
https://your-wisebasket-api.up.railway.app/health
https://your-wisebasket-api.up.railway.app/docs
```

8. Run database migrations against the production database before relying on planner endpoints.

## Production Checks

| Check | Expected result |
| --- | --- |
| `/health` | Returns status `ok`. |
| `/api/v1/health` | Returns API health plus food/data/backend status. |
| Database connection | API can read active foods and persist generated plans. |
| Production configuration validation | API refuses non-development startup if `JWT_SECRET`, `DATABASE_URL` or `CORS_ORIGINS` are unsafe defaults. |
| Mobile API URL | Mobile build uses the Railway public API URL. |

## Rollback Notes

Deploy compatible API and worker extraction packages and ensure inference returns the full transcript. Deploy API and mobile together for recipe total counts. Verify receipt extraction, review and confirmation in UAT; mocked regression checks do not prove real receipt accuracy. See [Iteration 2](../iteration-2.md).

If a deployment breaks:

1. Roll back to the previous successful Railway deployment.
2. Check health endpoint and logs.
3. Confirm no migration created incompatible schema state.
4. Fix through a pull request and redeploy.
