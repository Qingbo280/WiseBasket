# Web frontend on Cloudflare Pages

## Workers GitHub workflow (current Cloudflare Create an app screen)

Click Continue with GitHub and select the WiseBasket repository. Use root
directory `apps/mobile`, build command `npm run build:web`, and deploy command
`npx wrangler deploy`. Choose `develop` for the UAT deployment branch. Set the
build environment variables to the UAT API and R2 URLs listed below, and
`NODE_VERSION=22`. The checked-in `apps/mobile/wrangler.jsonc` configures
`wisebasket` to serve the exported `dist` assets with SPA fallback.
Set the Cloudflare Worker name to `wisebasket` to match this configuration.

These local changes must be committed and pushed before Cloudflare can use
them. After deployment, append the actual `workers.dev` and custom-domain
origins to the UAT API's CORS configuration. Browser verification and the
`develop` to `main` release process still apply. Production should use a
separate Worker name and the production API URL.

The Pages alternatives below are available via Continue to Pages on that
screen. They use a build output directory rather than a Worker deploy command.

WiseBasket's Expo app exports as a single-page website. The API remains on
Railway and food images remain on R2. No backend code is deployed to Pages.

## Build locally

The web preview displays its version and environment above the phone. Before
each release push, increment `WEB_APP_VERSION` in
`apps/mobile/src/config/webTestingRelease.ts`. Build that release twice with
the same version: set `EXPO_PUBLIC_APP_ENV=UAT` with the UAT API URL, and
`EXPO_PUBLIC_APP_ENV=PROD` with the production API URL in Cloudflare's build
variables. Environment labels are embedded at build time; rebuild after changing
them. An unset label recognizes the existing UAT API; other unset or invalid
labels display `LOCAL`. This version label is web-only and does not change
native app versions or UI.

From the repository root:

```bash
cd apps/mobile
npm ci
EXPO_PUBLIC_API_BASE_URL=https://wisebasket-uat-api.up.railway.app \
EXPO_PUBLIC_ASSET_BASE_URL=https://pub-dcfc9899ab7c4365bd3f9442a34680bb.r2.dev \
npm run build:web
```

The command validates public configuration, checks TypeScript and exports
`apps/mobile/dist`. Environment variables are embedded at build time; changing
the API URL requires rebuilding. Shell variables override local env files.
Never put secrets in `EXPO_PUBLIC_` variables.

## First UAT deployment: direct upload

In Cloudflare, open Workers & Pages, create a Pages application, and choose
direct upload. Upload the contents of `apps/mobile/dist` (or the ZIP containing
those contents), not the mobile source directory. Name the project
`wisebasket-uat` if available. Record the actual HTTPS URL Cloudflare assigns.

Alternatively, after installing and authenticating Wrangler, from `apps/mobile`:

```bash
npx wrangler pages deploy dist --project-name wisebasket-uat
```

Direct upload and Git integration are separate project creation choices. Choose
Git integration instead if automatic builds from the repository are desired.

## Git integration alternative

Use separate UAT and production Pages projects so each has a stable origin.

| Setting | UAT | Production |
| --- | --- | --- |
| Production branch | `develop` | `main` |
| Root directory | `apps/mobile` | `apps/mobile` |
| Build command | `npm run build:web` | `npm run build:web` |
| Output directory | `dist` | `dist` |
| `EXPO_PUBLIC_API_BASE_URL` | `https://wisebasket-uat-api.up.railway.app` | `https://wisebasket-prod.up.railway.app` |
| `EXPO_PUBLIC_ASSET_BASE_URL` | `https://pub-dcfc9899ab7c4365bd3f9442a34680bb.r2.dev` | Same |
| `NODE_VERSION` | `22` | `22` |

Avoid automatically exposing branch previews until their API environment and
CORS origins are intentionally configured. Changes go through `develop` and
UAT verification before release to `main`.

## Railway API CORS

Append each deployed frontend origin to the corresponding API service's
`CORS_ORIGINS`, preserving existing entries. Use an exact origin with scheme
and hostname, without a path or trailing slash. For example:

```dotenv
CORS_ORIGINS=https://wisebasket-uat.pages.dev
```

This example must be replaced with the actual allocated hostname and combined
with existing origins. Redeploy the API after updating the variable. Do not use
wildcards for preview deployments. Local browser development may require
`http://localhost:8081` in UAT's explicitly allowed origins.

## Custom domain and verification

In the Pages project's Custom domains tab, add the desired hostname and follow
Cloudflare's DNS instructions. Also add that HTTPS origin to API CORS. Add the
domain through Pages before configuring a standalone DNS record.

Test account registration/login, reload with a saved session, logout, images,
weekly planning, price checks, manual and GPS location, receipt upload, and
phone/desktop layouts on the deployed site. A successful export does not prove
these browser journeys work. HTTPS is required for browser location access.

Pages supplies SPA fallback when no top-level `404.html` is present; the Expo
single-page export intentionally does not create that file.

References:

- https://developers.cloudflare.com/pages/get-started/direct-upload/
- https://developers.cloudflare.com/pages/get-started/git-integration/
- https://developers.cloudflare.com/pages/configuration/serving-pages/
- https://developers.cloudflare.com/pages/configuration/custom-domains/
