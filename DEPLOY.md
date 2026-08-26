# Deploying RepoRevive

A step-by-step for taking RepoRevive live. Two pieces deploy independently and
are wired together at the end:

- **Backend** (this repo's `backend/`) — FastAPI on Render (or any Docker host).
- **Frontend** (`frontend/`) — a static Vite build on Vercel / Netlify / Render.

The backend is **stateless** (in-memory store) and reads all configuration from
environment variables, so it deploys cleanly to free tiers.

---

## 0. Prerequisites

- A GitHub account and an empty repo to push to.
- A Render account (or another Python host) for the backend.
- A static host (Vercel / Netlify / Render) for the frontend.
- Optional: a Gemini API key (for AI chat/narration/embeddings). Without it the
  backend runs deterministic-only.

---

## 1. Push to GitHub

From the repo root:

```bash
git remote add origin https://github.com/<you>/reporevive.git
```
```bash
git push -u origin main
```

> `.env` and `node_modules/` are git-ignored — secrets and build artifacts won't
> be pushed. Double-check nothing sensitive is staged before the first push.

---

## 2. Deploy the backend (Render Blueprint)

The Blueprint lives at the repo root: [`render.yaml`](render.yaml).

1. Render dashboard → **New → Blueprint** → connect the GitHub repo.
2. Render reads `render.yaml` and provisions the `reporevive-backend` web service
   (`rootDir: backend`, health check `/health`). The build installs both
   `requirements.txt` and `requirements-ai.txt` so AI works in production.
3. Set the env vars marked `sync: false` in the dashboard:
   - `GEMINI_API_KEY` — your key (leave blank for deterministic-only).
   - `FRONTEND_ORIGIN` — fill in **after** step 3 (the frontend URL).
    - `GITHUB_TOKEN` — optional; public repos only.
    - `REQUIRE_OWNER_TOKEN=true` — enabled by the provided Blueprint; the frontend
      keeps the per-analysis token in memory and sends it on scoped requests.
    - (`GEMINI_MODEL`, `EMBEDDING_MODEL`, `RETRIEVAL_MODE` have sensible defaults;
     set `RETRIEVAL_MODE=embeddings` for semantic chat — it uses AI quota.)
4. Deploy. Note the backend URL, e.g. `https://reporevive-backend.onrender.com`.

**Docker alternative** (Railway / Fly / any container host):

```bash
docker build -t reporevive-backend backend
```
```bash
docker run -p 8000:8000 --env-file backend/.env reporevive-backend
```

The container respects the platform's `$PORT` and defaults to 8000.

---

## 3. Deploy the frontend

The frontend is a standard Vite app: build with `npm run build` → output in
`frontend/dist`. On Vercel/Netlify/Render, set the project root to `frontend`.

- **Build command:** `npm ci && npm run build`
- **Publish/output directory:** `dist`
- **Env var:** `VITE_API_BASE_URL` = the backend URL from step 2.

> `VITE_*` vars are baked in at **build time**, so set `VITE_API_BASE_URL` before
> building. If you change it later, rebuild the frontend.
>
> For SPA routing, add a catch-all rewrite to `/index.html` (Vercel/Netlify do
> this automatically for Vite; on Render add a rewrite rule `/* → /index.html`).

Note the frontend URL, e.g. `https://reporevive.vercel.app`.

---

## 4. Wire CORS (connect the two)

Back in the backend host, set:

- `FRONTEND_ORIGIN` = the frontend URL from step 3 (comma-separated if several).

Redeploy the backend so it picks up the new origin. This is what lets the
browser call the API (the backend only allows the configured origins).

---

## 5. Verify live

- `https://<backend>/health` → `{"status":"ok", ...}`
- `https://<backend>/docs` → interactive OpenAPI docs
- Open the frontend, submit a public GitHub URL or a ZIP, and confirm the
  dashboard, findings, roadmap, and chat render from real responses.

---

## Notes and gotchas

- **Free-tier cold starts:** Render's free web service spins down when idle;
  the first request after idle takes ~30–60s. The frontend's polling handles the
  wait, but the initial analysis may feel slow.
- **In-memory state:** analyses live in process memory and are lost on restart /
  spin-down. Fine for a demo; add persistence (Supabase) if you need durability.
- **AI cost:** with a key set and `RETRIEVAL_MODE=embeddings`, each analysis
  embeds every file chunk. Keep `lexical` (default) to avoid per-analysis embed
  calls; chat still works (keyword-based).
- **Rate limits:** POST endpoints are rate-limited per client (analyze/upload
  10/min, chat 30/min); status polling is exempt. Tune via `RATE_LIMIT_*`.
- **Secrets:** only ever set keys in the host's env settings or `backend/.env`
  (git-ignored) — never in `.env.example` (committed).
