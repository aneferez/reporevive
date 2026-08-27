# Android APK — hand-off to Codex

**Audience:** Codex (owns the mobile/APK track)
**From:** backend + deploy (Claude)
**Date:** 2026-08-27
**Goal:** ship an Android **APK** for RepoRevive.

---

## What RepoRevive is today

A **React + Vite + TypeScript** web app (`frontend/`) talking to a **FastAPI**
backend (`backend/`). Both are **live on Render**, served from **one origin**:

- **App (single URL):** `https://reporevive-frontend.onrender.com`
  - The static site **proxies** `/api/*`, `/health`, `/docs`, `/openapi.json` to
    the backend (`render.yaml` → `reporevive-frontend` `routes`). So from the
    web, everything is same-origin and there is **no CORS** in play.
- Backend (direct, if ever needed): `https://reporevive-backend-6twt.onrender.com`

There is **no Android project yet** — the APK is a *wrapping* job, not a rewrite.

## Recommended approach: Capacitor around the Vite build

1. `cd frontend && npm i -D @capacitor/cli && npm i @capacitor/core @capacitor/android`
2. `npx cap init RepoRevive com.reporevive.app --web-dir=dist`
3. In `capacitor.config.ts`, keep `webDir: "dist"`. Do **not** set `server.url`
   (bundle the assets into the app; don't point the webview at the live site).
4. Build the web bundle, then add + sync Android:
   - `npm run build`  (Vite → `dist`)
   - `npx cap add android`
   - `npx cap sync android`
5. Build the APK (needs the toolchain below):
   - Debug: `cd android && ./gradlew assembleDebug` → `android/app/build/outputs/apk/debug/app-debug.apk`
   - Release: `./gradlew assembleRelease` (signed — see below)

## The one integration detail that will bite: CORS from the webview

The combined URL removes CORS **for the website** (same-origin), but a Capacitor
app's webview has its **own** origin (`https://localhost` on Android with the
default `androidScheme: "https"`), so its calls to the API are **cross-origin**.
Two clean options — pick one:

- **(A) Native HTTP (recommended):** add `@capacitor/http`. It routes
  `fetch`/`XHR` through the native layer, which **bypasses browser CORS**
  entirely. No backend change needed. The existing API client in
  [`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts) keeps working as-is.
- **(B) Allow the app origin on the backend:** add `https://localhost` (and, if
  you switch schemes, `capacitor://localhost`) to the backend's
  **`FRONTEND_ORIGIN`** env var on Render (comma-separated). Ask the backend
  owner (this repo) to add it — `FRONTEND_ORIGIN` is an exact-match, no-trailing-
  slash list ([`backend/app/config.py:91`](../backend/app/config.py)).

## API base URL for the mobile build

Point the app at the single combined URL:

```
VITE_API_BASE_URL=https://reporevive-frontend.onrender.com
```

(Directly using the backend URL also works, but the combined URL keeps it to one
host.) `VITE_*` is baked in at **build time**, so set it before `npm run build`.

## Owner-token (already handled in the shared client)

The backend runs with `REQUIRE_OWNER_TOKEN=true`. The web client already stores
the one-time `owner_token` from analysis creation and sends it as the
`X-Owner-Token` header on scoped requests — that same code ships inside the
webview, so nothing extra is needed. Just confirm the header survives whichever
HTTP path you choose in (A)/(B) above.

## Build prerequisites (not on the repo machine)

- **Android SDK** (`ANDROID_HOME` / `ANDROID_SDK_ROOT`) — not installed here.
- **JDK 17** — the repo machine has **JDK 11**, which is too old for current
  Android Gradle Plugin. Install JDK 17.
- Gradle comes via the wrapper (`./gradlew`), no separate install needed.

## Signing

- **Debug** APK is auto-signed with a throwaway debug keystore — fine for testing.
- **Release** APK needs a keystore the **owner** generates
  (`keytool -genkeypair …`) and keeps secret. **Do not commit the keystore or its
  passwords**; wire them via `android/keystore.properties` (gitignored) or Gradle
  env vars.

## Definition of done

- `app-debug.apk` installs and runs against the live API (analysis, findings,
  roadmap, chat all work from the device).
- Owner-token requests succeed (no 403 from the device).
- For distribution: a signed `app-release.apk` (or an `.aab` for Play).
