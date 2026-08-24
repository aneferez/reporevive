from __future__ import annotations

from .helpers import make_zip

# A deliberately broken repo exercising several analyzers at once.
_BROKEN_REPO = {
    "frontend/package.json": b'{"dependencies":{"react":"18","react-dom":"18"},"devDependencies":{"vite":"5"}}',
    "frontend/src/api.ts": (
        b'const base = "http://localhost:8000";\n'
        b'export const search = () => fetch("/api/jobs/search", { method: "POST" });\n'
    ),
    "backend/main.py": (
        b"from fastapi import FastAPI\n"
        b"import os\n"
        b"app = FastAPI()\n\n"
        b'TOKEN = os.getenv("SECRET_TOKEN")\n\n'
        b'@app.get("/api/jobs")\n'
        b"def jobs():\n"
        b"    return []\n"
    ),
    "backend/config.py": b'AWS_KEY = "AKIA1234567890ABCDEF"\n',
    # No README, no tests, no deploy config, no .env.example.
}


def _analyze(client) -> str:
    resp = client.post(
        "/api/repositories/upload",
        files={"file": ("broken.zip", make_zip(_BROKEN_REPO), "application/zip")},
    )
    assert resp.status_code == 202
    return resp.json()["analysis_id"]


def test_broken_repo_produces_expected_findings(client):
    analysis_id = _analyze(client)

    summary = client.get(f"/api/analysis/{analysis_id}").json()
    assert summary["status"] == "completed"
    assert summary["stack"]["frontend"][:2] == ["React", "Vite"]
    assert "FastAPI" in summary["stack"]["backend"]
    assert summary["summary"]["readiness_label"] in {"needs_attention", "not_ready"}

    findings = client.get(f"/api/analysis/{analysis_id}/findings").json()["items"]
    categories = {f["category"] for f in findings}
    assert "api_mismatch" in categories
    assert "secret" in categories
    assert "documentation" in categories
    assert "testing" in categories
    assert "configuration" in categories

    # Findings are sorted most-severe first and have stable ids.
    assert findings[0]["id"] == "finding_001"
    severities = [f["severity"] for f in findings]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    assert severities == sorted(severities, key=lambda s: order[s])

    # Every finding carries evidence-backed structure.
    for f in findings:
        assert f["recommendation"]
        assert 0.0 <= f["confidence"] <= 1.0


def test_broken_repo_architecture_and_roadmap(client):
    analysis_id = _analyze(client)

    arch = client.get(f"/api/analysis/{analysis_id}/architecture").json()
    comp_ids = {c["id"] for c in arch["components"]}
    assert "frontend" in comp_ids
    assert "backend" in comp_ids
    assert any(c["source"] == "frontend" and c["target"] == "backend" for c in arch["connections"])

    roadmap = client.get(f"/api/analysis/{analysis_id}/roadmap").json()["items"]
    assert roadmap
    # High-priority tasks come first.
    priorities = [t["priority"] for t in roadmap]
    rank = {"high": 0, "medium": 1, "low": 2}
    assert priorities == sorted(priorities, key=lambda p: rank[p])
    # Roadmap links back to findings.
    assert any(t["related_finding_ids"] for t in roadmap)


def test_report_bundles_everything(client):
    analysis_id = _analyze(client)
    report = client.get(f"/api/analysis/{analysis_id}/report").json()
    assert report["overview"]
    assert report["findings"]["total"] >= 4
    assert report["roadmap"]["items"]
    assert report["limitations"]
