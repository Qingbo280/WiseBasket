# Project review — 2026-09-18

Historical snapshot: these findings were recorded against commit `f0a68af`
and the deployment configuration available at that time. The project has
since changed, including web-specific screens and receipt integration; this
document is not a current readiness report. Revalidate each finding against
the latest code before acting on it. The native intro edits described below
have been removed in favour of the separate web implementation.

Reviewed the tracked deployment files, mobile startup/navigation, API clients,
authentication and pantry/receipt flows, backend configuration/authentication/
ownership checks, migration chain, worker packaging, and CI. This is a targeted
code review and test run, not a claim that every line or browser journey has
been verified. No shared Railway database was modified.

## Confirmed findings

### P1 — UAT rejects the deployed frontend origin

A live OPTIONS request to the UAT login endpoint, with origin
`https://wisebasket.rboo0006.workers.dev`, returned HTTP 400 and
`Disallowed CORS origin`, without an allow-origin header. Browser login and
other cross-origin API calls cannot work with this configuration.

Append this exact origin to the UAT Railway API service's `CORS_ORIGINS`,
preserving existing origins, and redeploy the API. Repeat for any custom domain
and whichever backend the build actually targets. See
`services/api/app/main.py:176` for middleware wiring.

### P1 — Receipt scanning is still a demo frontend flow

`ReceiptProcessingScreen.tsx:57` advances after a fixed 1.2-second timer.
`ReceiptReviewScreen.tsx:42` defines fixed garlic/onion/chicken/rice/salt lines,
and line 107 initializes the review from those fixtures. The image selected in
`App.tsx:775` is displayed but never uploaded to the backend receipt endpoint.
Confirmation at `App.tsx:1170` only updates frontend state.

Every image can therefore produce the same supposed receipt items. Connect
upload, status polling, review lines, and confirmation to the existing owned
receipt API; display processing/failure states from the server. Until then,
this feature should not be presented as working OCR.

### P1 — Account changes leave previous basket/receipt state mounted

`App.tsx:447` logs out and changes screens, but does not reset the planning,
receipt, shopping-item, and recent-check state owned by TestFlow. For example,
`receiptHaveItems` at line 191 is outside AuthProvider. Signing into another
account in the same tab can retain the previous session's temporary items.

Reset account-specific flow state on logout/session expiration/account change,
or mount it under an account-scoped key. Coordinate guest-to-account draft
handoff separately so intentional guest selections can still be preserved.

### P2 — Native confirmation alerts do nothing in the browser

`MyBasketMainScreen.tsx:382` and line 392 use `Alert.alert` to confirm consuming
and removing items. The installed react-native-web Alert implementation is
`static alert() {}`. Those confirmation callbacks never run on web. Camera and
library error alerts in `App.tsx:785` and line 794 are also silent there.

Use a shared dialog/inline error implementation that supports both web and
native. This is separate from pantry persistence below.

### P2 — Pantry modifications only change screen state

`MyBasketMainScreen.tsx:677`, line 683, and line 687 hide consumed/removed items
or override quantities locally. They do not update owned pantry records through
the API. MyBasketMainScreen unmounts when another screen is shown, so edits are
lost on return; reload and another device also restore the old pantry state.

Connect these actions to pantry write endpoints and refresh/cache the returned
records. Distinguish persisted pantry items from temporary recipe/guest items.

### P2 — Refresh requests lack timeout and clear sessions on server errors

`src/services/api.ts:126` performs refresh with an unbounded fetch, unlike
normal API requests. At line 133 every non-OK result clears tokens, including
temporary HTTP 500/502/503 errors. An expired access token during an outage can
either hang a request or sign out a valid user.

Add bounded cancellation and user-safe errors; revoke local credentials only
when the backend identifies the refresh token as invalid. The current shared
refresh promise correctly avoids duplicate refreshes within one JS runtime.

### P2 — Desktop intro controls depend on a cropped portrait bitmap

`IntroScreen.tsx:97` stretches a portrait poster using cover. At desktop aspect
ratios the poster is cropped, while invisible Skip/Next targets remain anchored
to viewport corners. Baked controls can disappear or no longer match their hit
areas. The height correction does not solve this aspect-ratio mismatch.

Use a bounded portrait intro surface or real responsive controls. Verify both
wide desktop and narrow phone layouts before calling the web flow complete.

### P2 — CI checks types but does not run frontend tests or web export

`.github/workflows/ci.yml:61` installs the mobile app and checks TypeScript only.
The 227 existing frontend tests and production web export are absent. Several
screen tests check source strings rather than rendering behavior; they can pass
despite the receipt demo flow and browser layout failures.

Add the existing test suite and public-config web build to CI, plus focused
browser journey coverage for intro, auth, and pantry actions.

## Changes made during this deployment review

Intro pages now receive an explicit measured height so their images do not
depend on a collapsed percentage-height list item. Web scroll events now update
the current page, because the browser implementation does not emit native
momentum-end events. These changes remain local until committed and pushed.

## Documentation discrepancy

The root README describes an `apps/admin` Next.js dashboard, but no admin source
files are tracked in this checkout. Only ignored build/dependency directories
exist locally. Reconcile the README with the actual dashboard repository or
restore its source if it is intended to be part of this project.

## Validation

- Frontend: 227 tests passed, zero failed.
- Public UAT environment validation, TypeScript, and Expo web export passed.
- Python source compilation passed.
- Alembic has one head (`n6o7p8q9r0s`); all migrations applied successfully to
  a new isolated local PostgreSQL database using migrations only before the
  test suite's own fixtures ran.
- Full backend suite: 532 passed, one skipped, zero failed (33.05 seconds).
  The 84 warnings concern existing test JWT key lengths and deprecated APIs;
  they are not test failures.
- No browser DOM/interaction verification was performed. Export success and
  source-level checks do not establish that hosted user journeys work.
- The first backend attempt was stopped at conftest import by the project's
  remote-database guard; tests were subsequently redirected to an isolated
  local test container. The guard was not bypassed.
