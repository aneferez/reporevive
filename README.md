# RepoRevive

**Understand. Diagnose. Revive.**

RepoRevive is an AI-assisted repository analysis and recovery tool. Point it at a
public GitHub repository or upload a source ZIP, and it identifies the technology
stack, surfaces evidence-backed engineering issues, produces a prioritized
recovery roadmap, and answers questions about the codebase with citations.

> Repositories are **inspected, not executed**. Findings are advisory, suspected
> secrets are redacted, and uncertain conclusions are marked as such.

See [`RepoRevive_PRD.md`](RepoRevive_PRD.md) for the full product spec and the
frozen API contract.

## Repository layout

```text
backend/     FastAPI backend — repository intake, analyzers, retrieval, AI, API
frontend/    React + Vite frontend (separate owner) — not part of this backend
```

## Status

| Area | Owner | Status |
| --- | --- | --- |
| Backend (this repo's `backend/`) | Claude | Phases 1–6 implemented; 71 tests + 29 eval scenarios passing |
| Frontend | ChatGPT / Codex | Separate deliverable |
| Deployment & accounts | Aneruth G J | Configs provided; live deploy pending |

## Backend at a glance

- **Intake** — public GitHub tarball fetch (SSRF-guarded) and safe in-memory ZIP
  extraction (path-traversal/symlink/size/count limits), with secret redaction at
  storage time.
- **Deterministic analyzers** — stack detection, architecture graph, configuration
  inspection, API-contract comparison (frontend calls vs backend routes), masked
  secret detection, and tests/docs assessment. Every finding cites its evidence.
- **Retrieval + AI** — pluggable retrieval behind one interface: lexical BM25
  (default, offline), in-memory Gemini embeddings, or pgvector (Postgres;
  experimental). All power grounded, cited chat; the optional Gemini layer also
  adds narration and degrades gracefully when no key is set.
- **Safety** — no code execution, GitHub-only fetching, redaction before storage/
  logging/AI/response, structured errors, and explicit uncertainty on findings.

### Run the backend

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Health: <http://localhost:8000/health> · Docs: <http://localhost:8000/docs>

See [`backend/README.md`](backend/README.md) for full setup, environment
variables, testing, evaluation, and deployment details.

## API contract

The backend implements the endpoints defined in the PRD (§11), including
`POST /api/repositories/analyze`, `POST /api/repositories/upload`,
`GET /api/analysis/{id}` (+ `/architecture`, `/findings`, `/roadmap`, `/report`),
`POST /api/analysis/{id}/chat`, and `DELETE /api/analysis/{id}`. Interactive
OpenAPI docs are served at `/docs`.
