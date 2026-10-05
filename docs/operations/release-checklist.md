# Release Checklist

This checklist should be completed before a mentor review, production-facing branch handoff or public mobile build sharing.

## Repository

- [ ] Branch is the intended release branch.
- [ ] Before pushing a release change, increment `WEB_APP_VERSION` in `apps/mobile/src/config/webTestingRelease.ts`. Use the same version for UAT and PROD builds of that release.
- [ ] Web build sets `EXPO_PUBLIC_APP_ENV=UAT` or `PROD`, and its API URL matches that environment. Verify the version and environment above the phone preview.
- [ ] Working tree is clean.
- [ ] Removed scope is not visible as production scope.
- [ ] Root README and `docs/` agree on project structure.
- [ ] No `.env` file is committed.
- [ ] No secret values are present in tracked files.

## Backend

- [ ] Railway API deploys successfully.
- [ ] `/health` returns `ok`.
- [ ] `/api/v1/health` confirms backend and data availability.
- [ ] Database migrations have been applied.
- [ ] `JWT_SECRET` is strong and not default.
- [ ] `DATABASE_URL` points to the intended PostgreSQL service.
- [ ] Logs do not show startup errors.

## Mobile

- [ ] `EXPO_PUBLIC_API_BASE_URL` points to the intended API.
- [ ] `npm run typecheck` passes.
- [ ] App opens on target phone/emulator.
- [ ] Register/login works.
- [ ] Planning inputs can be completed.
- [ ] Plan generation succeeds for a normal test case.
- [ ] Infeasible case shows a clear message.
- [ ] Store recommendation appears or fallback is clear.

## Testing Evidence

- [ ] Automated backend tests pass.
- [ ] Mobile typecheck passes.


## Documentation

## Iteration 2 receipt and recipe checks

- [ ] API and worker use compatible full-text extraction code and inference returns raw OCR text.
- [ ] Receipt full-text extraction, parser fallback and RapidFuzz regression checks pass.
- [ ] Labelled real receipts show acceptable row, food, price and quantity accuracy in UAT.
- [ ] Receipt correction replaces an existing row; confirmation updates pantry.
- [ ] Recipe “Have it” works without a quantity and refreshes suggestions.
- [ ] Recipe badges include optional ingredients and handle older API responses.
- [ ] Known local-only pantry-related state paths and pending ranking changes are documented.

## Documentation review

- [ ] System overview is current.
- [ ] API contract matches implemented endpoints used by the mobile app.
- [ ] Database architecture matches current migrations/models.
- [ ] Deployment docs match the actual Railway setup.
- [ ] Mobile build docs explain local phone and public API configuration.
- [ ] Known limitations are honest and scoped to future iterations.
