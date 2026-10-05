# GitHub Workflow

This document defines the WiseBasket repository workflow. It is intended for developers and project managers who need traceability between scope, code and tests.

## Branches

| Branch | Purpose |
| --- | --- |
| `develop` | Active integration branch for ongoing team work. |
| `main` | Stable release branch when ready. |
| `prod-ready` | Production-facing cleanup branch for public build preparation. |
| `feature/*` | Feature work tied to an epic, user story or technical task. |
| `chore/*` | Cleanup, repository maintenance and non-feature changes. |

## Pull Request Rules

Each pull request should include:

- purpose of the change;
- linked Epic, User Story and Acceptance Criteria where applicable;
- screenshots or evidence for user-facing changes;
- test commands run;
- known limitations or follow-up work.

## CI Checks

The current GitHub Actions workflow runs:

| Job | What it verifies |
| --- | --- |
| Backend test | Installs Python dependencies, runs Alembic migrations and executes pytest. |
| Mobile typecheck | Installs mobile dependencies and runs `npm run typecheck`. |

## Traceability Rule

Every meaningful implementation change should be traceable to at least one of:

- Epic number;
- User Story number;
- Acceptance Criteria number;
- bug or production readiness issue;
- mentor feedback item.

Recommended PR title examples:

```text
Epic 3.0: Add budget-constrained plan generation validation
AC 4.2.1: Add nearby store recommendation fallback
Chore: Remove non-production files from prod-ready branch
```

## Review Expectations

Reviewers should check:

- the change matches the stated scope;
- no removed or deferred feature is accidentally reintroduced;
- environment variables are not hardcoded;
- tests or evidence are included;
- docs are updated when setup, deployment, API or architecture behaviour changes.
