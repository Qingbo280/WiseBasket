# Mobile App Architecture

This document explains the Expo React Native mobile app used by WiseBasket Iteration 2. It is intended for frontend developers and assessors reviewing how the user-facing build is structured.

It covers app responsibilities, environment configuration, API integration and build readiness. It does not cover the removed admin dashboard.

## Technology Choice

| Technology | Why WiseBasket uses it |
| --- | --- |
| Expo | Speeds up React Native development, supports Android/iOS previews, and reduces native setup work for a student team. |
| React Native | Allows one mobile codebase for Android and iOS-style testing. |
| TypeScript | Gives safer API models, navigation types and component props. |
| Expo SecureStore | Stores auth tokens more safely than plain local storage on mobile devices. |
| Expo Location | Supports current-location planning when the user chooses location-based store recommendation. |

## App Location

The mobile app is stored in:

```text
apps/mobile
```

Important files:

| File or folder | Purpose |
| --- | --- |
| `App.tsx` | Root app composition. |
| `src/screens/` | User journey screens such as login, budget, household, restrictions, location, food review and plan results. |
| `src/services/api.ts` | Shared API request helper, timeout handling, auth retry and configured API base URL. |
| `src/services/plannerApi.ts` | Planner-specific client functions and request mapping. |
| `src/auth/AuthProvider.tsx` | Authentication state and session restore. |
| `src/api/plannerTypes.ts` | TypeScript API contract types. |
| `src/data/foodAssetManifest.ts` | Food image metadata keyed by canonical backend IDs. |
| `src/services/recipePantry.ts` | Saves recipe ingredient presence without inventing quantities. |
| `src/services/recipeIngredientBadge.ts` | Counts available ingredients against the complete recipe total, with older-API fallback. |
| `src/services/receiptReviewRows.ts` | Presents catalogue names or unmatched placeholders and replaces foods within existing rows. |
| `assets/` | Icons, splash image and bundled food images. |

## Runtime Configuration

The mobile app reads its backend URL from:

```text
EXPO_PUBLIC_API_BASE_URL
```

The app intentionally has no hidden production fallback. If the variable is missing, API calls fail clearly with a configuration error. This is safer for public builds because the app cannot silently point to localhost or an old server.

Examples:

```env
# Public backend hosted on Railway
EXPO_PUBLIC_API_BASE_URL=https://your-wisebasket-api.up.railway.app

# Local physical phone testing
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.10:8000
```

## Data Ownership

The production mobile architecture treats the backend as the source of truth.

| Data area | Owner | Mobile use |
| --- | --- | --- |
| Selectable foods | Backend `/api/v1/foods` | Build the food picker directly from canonical backend rows. |
| Food names and categories | Backend `/api/v1/foods` | Display backend names and group by backend category. |
| Dietary exclusions | Backend `/api/v1/foods` | Hide foods using backend `exclusion_codes`. |
| Price, nutrition and pack data | Backend `/api/v1/foods` | Build catalogue and review displays from backend data. |
| Manual shopping areas | Backend `/api/v1/locations/supported` | Populate state/district pickers from active location rows. |
| Food images | Asset manifest and optional configured asset host | Attach presentation images by backend canonical food ID. |
| Planning/profile state | Mobile + backend profile endpoint | Store local session state and sync account profile snapshots. |
| Generated plan and store recommendation | Integration pending | The mobile client still calls retired `/api/v1/plans`; it must move to V2 only after the live provider is mounted. |

This boundary is deliberate. Production builds must not create food, price,
nutrition, location or recommendation data in the mobile codebase. The mobile
bundle may format and illustrate backend data, but it should not become a
second data source.

## User Journey Ownership

| User journey area | Mobile responsibility |
| --- | --- |
| Account access | Register, log in, restore session, log out and refresh expired access tokens. |
| Planning setup | Capture weekly budget, household size, restrictions, location and familiar foods. |
| Data review | Fetch the live food catalogue and store selected backend food IDs. |
| Plan generation | Current client call to `/api/v1/plans` receives HTTP 410 until the separately planned V2 integration. |
| Results | Show food plan, cost, nutrition summary, shopping list, substitution options and store recommendation. |
| Failure state | Show user-safe messages for infeasible plans, validation problems, timeout and connection failure. |

## API Request Behaviour

`src/services/api.ts` centralises API behaviour:

- trims trailing slashes from `EXPO_PUBLIC_API_BASE_URL`;
- attaches bearer access tokens when auth is required;
- refreshes access tokens on 401 responses;
- prevents concurrent refresh-token races by sharing one refresh promise;
- maps backend errors into user-safe messages;
- supports longer timeouts for plan generation.

## Production Readiness Notes

| Item | Current status |
| --- | --- |
| App name | `WiseBasket` |
| Expo slug | `wisebasket` |
| Android package | `com.wisebasket.app` |
| iOS bundle identifier | `com.wisebasket.app` |
| Auth token storage | Expo SecureStore |
| API URL fallback | Removed; explicit env required |
| Dev bypass login | Removed from production-facing mobile config |

## Validation

Recipe cards in My Basket and Meal Ideas open backend recipe details. Ingredient selection saves pantry presence and retains selections after a failed write. Pantry updates trigger suggestion refreshes; a request counter prevents older results overwriting newer suggestions. The ingredient badge includes optional ingredients and requires the API's new `ingredient_count` field for a denominator. Without a valid total, it shows the available count only.

Receipt rows hide raw OCR labels and display catalogue food names or `Cannot be matched`. Replacement retains row identity, quantity and price. Signed-in purchased ticks persist pantry presence and refresh recipes through serialised writes; guest ticks remain local. Consumed/removed/quantity overrides still have local-only paths; see [Iteration 2 limitations](../iteration-2.md).

`EXPO_PUBLIC_ASSET_BASE_URL` can configure hosted food images in addition to `EXPO_PUBLIC_API_BASE_URL`. Provider keys never belong in mobile public variables.

Run the mobile type check:

```bash
cd apps/mobile
npm ci
npm run typecheck
```

Run a local Expo preview:

```bash
cd apps/mobile
npx expo start
```
