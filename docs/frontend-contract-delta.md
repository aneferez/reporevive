# Frontend ↔ Backend contract delta

**Audience:** frontend owner (ChatGPT / Codex)
**From:** backend (Claude)
**Date:** 2026-08-24
**Scope:** cross-check of `frontend/src/lib/api.ts` + `frontend/src/types.ts` against
the implemented backend and the PRD API contract (§11).

---

## TL;DR

The integration is sound. **All 9 endpoints, HTTP methods, request bodies, and the
error envelope match exactly.** The differences below are response **field
value/shape** drift in the frontend's TypeScript types. Only one caused a visible
bug, and the backend already fixed that one. The rest are type-accuracy fixes that
prevent future breakage — no endpoint or request changes are needed on either side.

---

## Already fixed on the backend

**Architecture component `type`: `database` → `persistence`.**
The backend was emitting `type: "database"`, but PRD §9 ("frontend, backend,
**persistence**, external service, deployment") and your `ArchitectureIcon` switch
use `persistence`. The DB node was falling back to the generic icon with no
styling. The backend now emits `type: "persistence"` (the node `id` stays
`"database"` so connection `target`s still resolve). **No frontend change needed.**

---

## Action items (frontend `types.ts`)

None of these break the app today (your UI is tolerant), but the types are
inaccurate and will cause silent drift as features are surfaced.

### 1. `FindingCategory` — add `secret`, drop the ones the backend never sends

The backend emits these category strings: `stack`, `configuration`, `api_mismatch`,
`secret`, `testing`, `documentation`, `dependency`, `deployment`, `architecture`.
Your union has `security` and `other`, which the backend never emits, and is missing
`secret` (used for all credential findings).

```diff
 export type FindingCategory =
   | "api_mismatch"
   | "configuration"
-  | "security"
+  | "secret"
   | "testing"
   | "documentation"
   | "dependency"
   | "deployment"
-  | "other";
+  | "stack"
+  | "architecture"
+  | (string & {});   // tolerate future categories without a type break
```

Works today only because your findings filter is derived from the data
(`new Set(items.map(f => f.category))`). Keep that pattern.

### 2. `RoadmapTask.estimated_complexity` — values are `low | medium | high`

Backend emits `low | medium | high`; your type says `small | medium | large`.
Not rendered yet, so no visible bug — but align before you surface it.

```diff
-  estimated_complexity: "small" | "medium" | "large" | string;
+  estimated_complexity: "low" | "medium" | "high" | (string & {});
```

### 3. `Severity` — backend enum can include `info`

The backend `Severity` enum allows `info` (not currently emitted in findings, and
never in `findings_by_severity`, which stays 4 keys). Add it defensively:

```diff
-export type Severity = "critical" | "high" | "medium" | "low";
+export type Severity = "critical" | "high" | "medium" | "low" | "info";
```

Note: `findings_by_severity` remains exactly `{critical, high, medium, low}`.

### 4. Treat two fields as nullable

The backend response schema allows these to be `null` (currently always populated,
but the schema permits absence):

```diff
 export interface Finding {
   ...
-  evidence: string;
+  evidence?: string | null;
 }

 export interface ArchitectureConnection {
   ...
-  label: string;
+  label?: string | null;
 }
```

### 5. `AnalysisReport` — the report response is **flat**, not nested

`GET /api/analysis/{id}/report` returns a flat object, not `{ analysis, architecture,
findings, roadmap, limitations }`. Today this is harmless because `ReportView` pulls
its data from the per-endpoint calls and only reads `report.limitations` (which the
flat response includes). But your type is inaccurate and you're leaving useful fields
(`overview`, `readiness_label`, `generated_at`) unused. The pinned shape is now in
PRD §11 ("Complete report response"). Suggested type:

```ts
export interface AnalysisReport {
  analysis_id: string;
  status: AnalysisStatus;
  repository: RepositoryIdentity;
  overview: string;
  readiness_label: string;
  stack: StackSummary;
  summary: AnalysisSummary;
  architecture: ArchitectureResponse;
  findings: FindingsResponse;
  roadmap: RoadmapResponse;
  limitations: string[];
  generated_at: string;
}
```

If you adopt this, you can drop the per-endpoint re-fetch in `ReportView` and read
`overview` / `readiness_label` straight from the report.

---

## Harmless (no action needed)

- `RoadmapTask.priority` allows `critical`; backend only sends `high | medium | low`.
- `ArchitectureComponentType` includes `external_service` / `unknown`; backend
  currently emits only `frontend | backend | persistence | deployment`.
- Backend adds an optional `progress: number` to the status response — safe to ignore
  or use for the progress bar.

---

## What matched (no changes)

- Endpoints, methods, and request bodies: `analyze {repository_url}`, `upload`
  multipart field **`file`**, `chat {question}`, `DELETE`, and all GETs.
- Error envelope `{ error: { code, message, request_id } }`.
- `VITE_API_BASE_URL`; states `queued | running | completed | failed`; stage strings
  (`config_checks`, `api_analysis`, `secret_checks`, …).
- Start / Summary / Findings / Chat / Roadmap / Architecture field names.
