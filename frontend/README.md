# RepoRevive frontend

React + Vite + TypeScript frontend for the RepoRevive standalone application.

## Commands

```powershell
npm install       # install frontend dependencies
npm run dev       # start BOTH the frontend (Vite) and the backend (FastAPI)
npm run dev:web   # start only the frontend (Vite)
npm run lint      # type-check
npm test          # unit tests
npm run build     # production build
```

## Android APK

The Android wrapper uses Capacitor and bundles the Vite output locally. It does
not load the hosted website inside the app. Android builds require JDK 17 and
an installed Android SDK (`ANDROID_HOME` or `ANDROID_SDK_ROOT`).

```powershell
# Use the combined Render origin for the mobile build.
$env:VITE_API_BASE_URL = "https://reporevive-frontend.onrender.com"
npm run build
npx cap sync android
cd android
.\gradlew.bat assembleDebug
```

The debug APK is written to
`android/app/build/outputs/apk/debug/app-debug.apk`. The release build requires
an owner-managed keystore; keep `keystore.properties`, passwords, and keystore
files out of version control. Capacitor's built-in `CapacitorHttp` plugin is
enabled in `capacitor.config.ts` so the webview can call the HTTPS API without
requiring a backend CORS change.

### `npm run dev` — one command for both servers

`npm run dev` runs [`scripts/dev.mjs`](scripts/dev.mjs), which launches the Vite
dev server **and** the FastAPI backend together and stops both on Ctrl+C (if
either process exits, the other is torn down too). No extra dependency — just Node.

- The backend runs with `uvicorn --reload` from `../backend`, preferring the
  project virtualenv at `../backend/.venv` and falling back to the system Python.
  Create the venv first if you haven't:
  `cd ../backend && python -m venv .venv && pip install -r requirements-dev.txt`.
- Vite serves on `http://localhost:5173` (or the next free port); the backend on
  `http://localhost:8000`. The app calls the backend via `VITE_API_BASE_URL`
  (default `http://localhost:8000`), so the two connect out of the box.
- Override the backend port with `BACKEND_PORT=<port>` if 8000 is taken.
- Use `npm run dev:web` when the backend is already running elsewhere.

## Environment

Copy `.env.example` to `.env.local`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_DEMO_MODE=false
```

`VITE_DEMO_MODE` is reserved for intentional sample UI review. The built-in sample is also available from the landing page without enabling it.

## API boundary

Requests are defined in `src/lib/api.ts` and use the exact endpoint paths in the PRD. The client expects the backend to provide:

```text
GET    /health
POST   /api/repositories/analyze
POST   /api/repositories/upload
GET    /api/analysis/{analysis_id}
GET    /api/analysis/{analysis_id}/architecture
GET    /api/analysis/{analysis_id}/findings
GET    /api/analysis/{analysis_id}/roadmap
POST   /api/analysis/{analysis_id}/chat
GET    /api/analysis/{analysis_id}/report
DELETE /api/analysis/{analysis_id}
```

The client treats the analysis service as authoritative for live data and uses the sample fixtures only after the user explicitly selects the sample path.

## Analysis ownership

The backend returns a one-time `owner_token` when a live analysis starts. The
frontend keeps that token in the current browser session and automatically sends it as the
`X-Owner-Token` header on status, result, chat, and delete requests. Sample mode
does not use an owner token. Refreshing the browser now restores the current
analysis when the backend still has it; the token is never shown in workspace
settings and is cleared when starting another analysis.
