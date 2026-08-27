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
- A Render account — one Blueprint deploys **both** services (backend web
  service + frontend static site).
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

## 2. Deploy both services (Render Blueprint)

The Blueprint lives at the repo root: [`render.yaml`](render.yaml). It defines
**two** services:

| Service | Type | Root | Serves |
| --- | --- | --- | --- |
| `reporevive-backend` | web (python) | `backend` | FastAPI API, health check `/health` |
| `reporevive-frontend` | static | `frontend` | Vite build (`dist`), SPA rewrite to `/index.html` |

1. Render dashboard → **New → Blueprint** → connect the GitHub repo.
2. Render reads `render.yaml` and provisions both services. The backend build
   installs `requirements.txt` + `requirements-ai.txt` (AI works in production);
   the frontend build runs `npm ci --include=dev && npm run build`.
3. Set the env vars marked `sync: false` when prompted:
   - **Backend** `GEMINI_API_KEY` — your key (leave blank for deterministic-only).
   - **Backend** `GITHUB_TOKEN` — optional; public repos only.
   - **Backend** `FRONTEND_ORIGIN` and **frontend** `VITE_API_BASE_URL` — leave
     these for **step 3** (each needs the other service's URL).
   - `REQUIRE_OWNER_TOKEN=true` is preset; the frontend sends the per-analysis
     `X-Owner-Token` on scoped requests. (`GEMINI_MODEL`, `EMBEDDING_MODEL`,
     `RETRIEVAL_MODE` have sensible defaults; `RETRIEVAL_MODE=embeddings` gives
     semantic chat but uses AI quota.)
4. Apply. Note both public URLs, e.g.
   `https://reporevive-backend.onrender.com` and
   `https://reporevive-frontend.onrender.com`.

**Docker alternative** for the backend (Railway / Fly / any container host):

```bash
docker build -t reporevive-backend backend
```
```bash
docker run -p 8000:8000 --env-file backend/.env reporevive-backend
```

The container respects the platform's `$PORT` and defaults to 8000.

---

## 3. Connect the two (set the cross-referencing URLs)

The browser reaches the backend over its **public** URL, so these two values are
set by hand after the first deploy, then each service redeploys:

- **Frontend** `VITE_API_BASE_URL` = the backend URL from step 2. This is baked
  in at **build time**, so saving it triggers a rebuild of the static site.
- **Backend** `FRONTEND_ORIGIN` = the frontend URL from step 2 (comma-separated
  if several). This is the CORS allowlist — the backend only answers browsers
  from these origins. Saving it redeploys the backend.

Wait for both redeploys to finish before verifying.

---

## 5. Verify live

- `https://<backend>/health` → `{"status":"ok", ...}`
- `https://<backend>/docs` → interactive OpenAPI docs
- Open the frontend, submit a public GitHub URL or a ZIP, and confirm the
  dashboard, findings, roadmap, and chat render from real responses.

### 5a. Owner-token enforcement (when `REQUIRE_OWNER_TOKEN=true`)

Start an analysis and capture the one-time `owner_token`, then confirm scoped
reads are gated:

```bash
curl -s -X POST https://<backend>/api/repositories/analyze \
  -H 'content-type: application/json' \
  -d '{"repository_url":"https://github.com/<owner>/<repo>"}'
# → { "analysis_id": "analysis_…", "owner_token": "…secret…", … }
```
```bash
# No header → 403 OWNER_TOKEN_INVALID
curl -s -o /dev/null -w '%{http_code}\n' https://<backend>/api/analysis/<id>/findings
# Correct header → 200
curl -s -o /dev/null -w '%{http_code}\n' \
  -H 'X-Owner-Token: <owner_token>' https://<backend>/api/analysis/<id>/findings
```

Expect `403` then `200`. (A *different* analysis's token must also return `403` —
that isolation guarantee is covered by `tests/test_ownership.py`.)

### 5b. pgvector retrieval (optional, when using a database)

If you provisioned Postgres+pgvector (e.g. Supabase) and want semantic chat,
set both `DATABASE_URL` and `RETRIEVAL_MODE=pgvector` on the backend service.
Validate the database from `backend/` first — the live integration test is
skipped unless `DATABASE_URL` is set, uses an isolated throwaway table, and
needs no AI key:

```bash
DATABASE_URL='postgres://…' pytest tests/test_pgvector_live.py -v
```

Expect one passing test (build → search → cleanup). Without `RETRIEVAL_MODE=pgvector`
the backend stays on the default lexical retriever and chat still works.

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
