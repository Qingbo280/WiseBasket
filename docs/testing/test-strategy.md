# Test Strategy

This document explains how WiseBasket repository tests support Iteration 2 quality. It is intended for developers, testers and assessors.

Detailed academic testing reports belong in the Google Drive `5.0 Testing` folder. This repo document explains where test assets live and how they should be run.

## Automated Test Coverage

The repository currently includes automated tests for areas such as:

- authentication and registration flow;
- API response behaviour;
- food catalogue access;
- budget and meal planning logic;
- optimizer feasibility;
- hard exclusions;
- price/store comparison;
- profile API;
- data-backed planner integration;
- validation and substitutions.

## Commands

Backend test suite:

```bash
pytest -c config/pytest.ini -q
```

Mobile TypeScript check:

```bash
cd apps/mobile
npm run typecheck
```

CI runs backend tests and mobile typecheck for pull requests and pushes to key branches.

## Acceptance Criteria Testing

Acceptance criteria testing should be written per epic so each requirement can be proven clearly.

Recommended evidence format:

| Field | Meaning |
| --- | --- |
| Epic | Epic number and title from the user story mapping. |
| User Story | User story number and statement. |
| Acceptance Criteria | AC number and expected behaviour. |
| Test Scenario | What the tester does. |
| Test Data | Inputs used. |
| Expected Result | What should happen. |
| Actual Result | What happened. |
| Status | Pending, Pass, Fail or Blocked. |
| Evidence | Screenshot, log, test run, PR, or file link. |

## Iteration 2 regression evidence

See [Iteration 2 validation](../iteration-2.md) for offline commands covering full-text extraction, parser fallback, grounded LLM extraction, RapidFuzz matching, repeated purchases, ingredient badges and pantry presence without quantities.

The most recent targeted OCR run passed 27 tests with mocked LLM responses. This is behavioural evidence, not a measured accuracy improvement or full release certification. Real receipt testing must compare missing/extra rows, food links, prices, quantities, false matches and latency against labelled baseline results.

Full backend tests use destructive fixtures: run only against a dedicated local or CI database with migrations applied, never against Railway. Shared extraction tests use `unittest`; inference tests use `--confcutdir=services/inference` to avoid application database fixtures.

## Internal Test Areas

Internal testing should cover:

- frontend screen flow and state transitions;
- backend endpoint validation and error handling;
- database migrations and integrity constraints;
- data mapping and quality rules;
- security checks for auth, secrets and role-protected routes.
