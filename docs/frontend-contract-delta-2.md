# Frontend ↔ Backend contract delta — follow-up (2 deferred items)

**Audience:** frontend owner (ChatGPT / Codex)
**From:** backend (Claude)
**Date:** 2026-08-27
**Scope:** the two `types.ts` items from
[`frontend-contract-delta.md`](frontend-contract-delta.md) that the backend did
**not** apply, because they require frontend *component* changes (not just type
edits) and are your call to make.

---

## Context

The backend applied the three safe, no-ripple type fixes directly (commit
`cb51d2c`): `FindingCategory` accuracy, `estimated_complexity` values, and
nullable `evidence` / connection `label`. The two items below were intentionally
left for you — each one touches rendering logic or demo data, so a blind type
edit breaks `tsc -b`.

Neither is required for the app to work today; both are correctness/robustness
improvements. Do them when convenient.

---

## Item A — add `info` to `Severity`

**Why:** the backend `Severity` enum includes `info`. It is **not** emitted in
findings today, and **never** in `findings_by_severity` (that object stays
exactly `{critical, high, medium, low}`). Adding it defensively means a future
`info` finding renders instead of crashing an exhaustive lookup.

**The catch:** `Severity` is used as an exhaustive key in three maps and one
index, so the type edit alone won't compile. All four spots need the `info` case.

### 1. The type (`src/types.ts`)

```diff
-export type Severity = "critical" | "high" | "medium" | "low";
+export type Severity = "critical" | "high" | "medium" | "low" | "info";
```

Leave `SeverityCounts` at four keys — the backend never sends `info` there.

### 2. `src/components/SeverityBadge.tsx`

```diff
 const labels: Record<Severity, string> = {
   critical: "Critical",
   high: "High",
   medium: "Medium",
   low: "Low",
+  info: "Info",
 };

 const icons = {
   critical: CircleX,
   high: AlertTriangle,
   medium: Info,
   low: CircleCheck,
+  info: Info,   // `Info` is already imported at the top of the file
 };
```

### 3. `src/App.tsx` — `SeverityBar` (~line 432)

```diff
-  const names = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };
+  const names = { critical: "Critical", high: "High", medium: "Medium", low: "Low", info: "Info" };
```

### 4. `src/App.tsx` — overview severity bars (~line 412)

`counts` is a `SeverityCounts` (four keys), but the map casts the array to
`Severity[]`, so `counts[severity]` stops type-checking once `info` exists.
Narrow the array to the counts' own keys — `keyof SeverityCounts` is still
assignable to `SeverityBar`'s `severity: Severity` prop:

```diff
-{(["critical", "high", "medium", "low"] as Severity[]).map((severity) =>
+{(["critical", "high", "medium", "low"] as (keyof SeverityCounts)[]).map((severity) =>
   <SeverityBar key={severity} severity={severity} count={counts[severity]} total={Math.max(totalFindings, 1)} />)}
```

### 5. CSS (optional but recommended)

The badge/bar use `severity-${severity}`, `dot-${severity}`, `fill-${severity}`
class names. Add an `info` variant in `src/index.css` (a muted/neutral tone) so a
real `info` finding is styled rather than falling back to an unstyled element.

---

## Item B — flatten `AnalysisReport`

**Why:** `GET /api/analysis/{id}/report` returns a **flat** object (pinned in PRD
§11), not `{ analysis, architecture, findings, roadmap, limitations }`. The
current nested type is inaccurate and leaves `overview` / `readiness_label` /
`generated_at` unused. Harmless today only because `ReportView` reads its data
from the per-endpoint calls and only touches `report.limitations`.

### 1. The type (`src/types.ts`)

```diff
-export interface AnalysisReport {
-  analysis?: AnalysisSummaryResponse;
-  architecture?: ArchitectureResponse;
-  findings?: FindingsResponse;
-  roadmap?: RoadmapResponse;
-  limitations?: string[];
-}
+export interface AnalysisReport {
+  analysis_id: string;
+  status: AnalysisStatus;
+  repository: RepositoryIdentity;
+  overview: string;
+  readiness_label: string;
+  stack: StackSummary;
+  summary: AnalysisSummary;
+  architecture: ArchitectureResponse;
+  findings: FindingsResponse;
+  roadmap: RoadmapResponse;
+  limitations: string[];
+  generated_at: string;
+}
```

This mirrors the backend `ReportResponse` field-for-field
(`backend/app/api/routes/analysis.py::get_report`).

### 2. Fix the two consumers in `src/App.tsx`

- **`demoReport` (~line 79)** is built with the old nested keys and will no
  longer type-check. Rebuild it against the flat shape (it already has
  `demoAnalysis`, `demoArchitecture`, `demoFindings`, `demoRoadmap` to draw
  from — pull `overview` / `readiness_label` / `summary` from `demoAnalysis`, and
  set a `generated_at`).
- **`ReportView` (~line 510)** still compiles (it reads `report.limitations`,
  which the flat shape includes). **Optional payoff:** you can now drop the
  per-endpoint re-fetch and read `overview` / `readiness_label` straight from
  `report`, and the JSON export (~line 515) becomes the real report bundle.

---

## Summary

| Item | Files touched | Blocking? |
| --- | --- | --- |
| A — `info` severity | `types.ts`, `SeverityBadge.tsx`, `App.tsx` (×2), `index.css` | No — defensive |
| B — flat `AnalysisReport` | `types.ts`, `App.tsx` (`demoReport`, optionally `ReportView`) | No — accuracy + unlocks unused fields |

Verify with `npm run lint` (`tsc -b`), `npm test`, and `npm run build` — the same
gates the backend ran for the three fixes it already landed.
