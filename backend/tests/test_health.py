from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["ai_enabled"] is False  # no key configured in tests
    assert resp.headers.get("X-Request-ID")


def test_openapi_available(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    for path in [
        "/health",
        "/api/repositories/analyze",
        "/api/repositories/upload",
        "/api/analysis/{analysis_id}",
        "/api/analysis/{analysis_id}/architecture",
        "/api/analysis/{analysis_id}/findings",
        "/api/analysis/{analysis_id}/roadmap",
        "/api/analysis/{analysis_id}/chat",
        "/api/analysis/{analysis_id}/report",
    ]:
        assert path in paths, f"missing contract path: {path}"
