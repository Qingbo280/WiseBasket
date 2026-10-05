# WiseBasket Documentation

This folder contains the technical documentation for the WiseBasket production-facing repository. It is written for three audiences:

- mentors and assessors who need to verify the build is orderly, maintainable and aligned with Iteration 2 scope;
- developers who need to run, test, deploy and extend the system;
- data and product teammates who need to understand how planning, food data and location recommendations connect.

The Google Drive reports remain the main academic submission artifacts. These repository docs support the build by explaining the implemented system, setup steps, technical decisions, data contracts, testing approach and production readiness checks.

## Documentation Map

| Area | Document | Use this when |
| --- | --- | --- |
| Current version | [Iteration 2](iteration-2.md) | You need current implemented behaviour, limitations and validation commands. |
| Architecture | [System Overview](architecture/system-overview.md) | You need the high-level technical picture of WiseBasket Iteration 2. |
| Architecture | [Production Runtime](architecture/production-runtime.md) | You need the strict production boundary before merge or deployment. |
| Architecture | [Mobile App Architecture](architecture/mobile-app.md) | You need to understand the Expo React Native app and its runtime configuration. |
| Architecture | [Backend API Architecture](architecture/backend-api.md) | You need to understand FastAPI, authentication, planner endpoints and service boundaries. |
| Architecture | [Database Architecture](architecture/database.md) | You need the database model, migration approach and data integrity controls. |
| Reference | [API Contract](reference/api-contract.md) | You need endpoint-level request and response details. |
| Reference | [Data Dictionary](reference/data-dictionary.md) | You need maintained data field definitions and source-data meaning. |
| Development | [Local Setup](development/local-setup.md) | You need to run WiseBasket locally. |
| Development | [GitHub Workflow](development/github-workflow.md) | You need branch, pull request, CI and traceability rules. |
| Deployment | [Railway Deployment](deployment/railway.md) | You need to deploy the backend API and PostgreSQL on Railway. |
| Deployment | [Mobile Build](deployment/mobile-build.md) | You need to configure Expo builds for phone testing or public API builds. |
| Deployment | [Cloudflare Web Frontend](deployment/web-cloudflare.md) | You need to build and host the Expo user app on Cloudflare Pages. |
| Testing | [Test Strategy](testing/test-strategy.md) | You need to understand what test folders exist and how evidence is collected. |
| Security | [Security Notes](security/security-notes.md) | You need the implemented security controls and remaining production risks. |
| Operations | [Release Checklist](operations/release-checklist.md) | You need a final checklist before mentor review or public build sharing. |

## Iteration 2 Scope

WiseBasket Iteration 2 includes:

1. Account registration and login.
2. Planning inputs: weekly budget, household size, location, dietary restrictions and usual basket.
3. Weekly food plan generation using deterministic optimisation.
4. Nearby store recommendation using available price and location data.
5. Pantry records, recipe suggestions, ingredient checking and household quantity summaries.
6. Receipt capture, PaddleOCR extraction, optional text LLM interpretation, catalogue matching and user confirmation.
7. Optional LLM selection of worth-considering foods, with curated display wording and deterministic fallback.

Planning costs, nutrition and store calculations remain deterministic. Text LLM interpretation is optional and does not establish receipt accuracy or prove pantry quantity sufficiency. See [Iteration 2](iteration-2.md) for the current boundary and pending work.

## Documentation Rules

- Keep repo docs technical and maintainable.
- Do not duplicate full academic reports from Google Drive.
- Do not document removed scope as production scope.
- Every build, deployment or test instruction should be runnable or clearly marked as pending.
- Every major technical claim should map back to code, data, tests, or a known project decision.
