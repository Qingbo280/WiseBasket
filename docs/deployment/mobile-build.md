# Mobile Build

This document explains how WiseBasket mobile builds should be configured for phone testing and public API builds. It is intended for frontend developers and release owners.

## Build Goal

The mobile app should connect to one explicit backend URL. For production/public builds, that URL should be the Railway API URL, not localhost.

## Required Environment Variable

```env
EXPO_PUBLIC_API_BASE_URL=https://your-wisebasket-api.up.railway.app
```

Expo exposes variables prefixed with `EXPO_PUBLIC_` to the app bundle, so only non-secret public configuration should use this prefix. Do not put API tokens, JWT secrets or database credentials in the mobile `.env`.

## Local Phone Testing

For physical phone testing on the same Wi-Fi network:

```env
EXPO_PUBLIC_API_BASE_URL=http://<PC_LAN_IP>:8000
```

Do not use `localhost` for a physical phone. On the phone, `localhost` means the phone itself, not the development computer.

## Public API Build

Use the Railway API URL:

```env
EXPO_PUBLIC_API_BASE_URL=https://your-wisebasket-api.up.railway.app
```

Then run:

```bash
cd apps/mobile
npm ci
npm run typecheck
npx expo start
```

Before sharing a public build, run:

```bash
cd apps/mobile
npm run prod:check
```

For packaged builds, use the team's chosen Expo/EAS workflow. Confirm the app opens, registers/logs in, saves planning inputs, generates a plan and displays store recommendation against the public API before sharing the build.

## Build Readiness Checklist

- [ ] `EXPO_PUBLIC_API_BASE_URL` points to the intended backend.
- [ ] No development bypass login variables remain.
- [ ] `npm run typecheck` passes.
- [ ] API `/health` passes before opening the app.
- [ ] Register and login work on a real device or emulator.
- [ ] Plan generation completes within expected timeout.
- [ ] Location permission message is correct.
- [ ] Store recommendation is shown or a clear fallback message appears.
