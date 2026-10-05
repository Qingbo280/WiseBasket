# Production Runtime Architecture

This document describes the Iteration 2 runtime supported by this checkout. Actual deployment status must be verified separately.

## Services

| Service | Responsibility |
| --- | --- |
| Expo mobile | Authentication, planning, pantry, recipes, receipt capture and review. |
| FastAPI | Household ownership, catalogue access, planning, store comparison and confirmation APIs. |
| PostgreSQL | Canonical data, users, plans, pantry, recipes and receipt drafts. |
| OR-Tools | Deterministic budget-constrained planning within the API process. |
| PaddleOCR inference | Recognition, row grouping and parser purchase drafts. |
| Redis and Celery worker/beat | Queued receipt extraction and scheduled data work when configured. |
| Optional text LLM | Constrained recommendations, full-transcript interpretation and label normalisation. |

Receipt processing uses the worker when a Redis broker is configured. Without a broker the API provides inline extraction, which still requires inference. Both paths use shared packages and the existing DeepSeek gateway.

## Data ownership

PostgreSQL remains the source for canonical foods, nutrition, prices, profiles, recipes and pantry records. Mobile manifests and an optional asset host provide presentation only. Numeric planning remains code-owned. LLM receipt amounts are validated against source text and remain subject to user review.

Database URLs, JWT secrets and provider keys stay server-side. Mobile public configuration includes `EXPO_PUBLIC_API_BASE_URL` and optional `EXPO_PUBLIC_ASSET_BASE_URL`.

## Release dependencies

- Deploy API and mobile together for recipe totals; older responses use the available-count fallback.
- Deploy compatible API and worker extraction packages and verify inference returns the full OCR transcript.
- Configure `INFERENCE_URL` in API and worker and shared `REDIS_URL` for queued execution.
- Enable `LLM_ENABLED` and configure DeepSeek credentials for text interpretation. Disabled or unavailable LLM execution retains parser fallback.
- Keep services on compatible shared-package versions.

## Readiness

Apply reviewed migrations, verify health and run targeted checks, then exercise authentication, planning, pantry, recipe refresh and receipt confirmation in the intended environment. Database test fixtures must not target shared deployments.

Mocked LLM tests do not prove OCR accuracy. Compare labelled real receipts against the deterministic baseline before claiming improvement. See [Iteration 2](../iteration-2.md) for commands, limits and pending work.
