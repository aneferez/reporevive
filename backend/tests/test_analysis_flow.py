from __future__ import annotations

from .helpers import make_zip


def _start_github(client) -> str:
    # GitHub fetch is stubbed offline by the _no_network fixture.
    resp = client.post(
        "/api/repositories/analyze",
        json={"repository_url": "https://github.com/example/example-project"},
    )
    assert resp.status_code == 202
    return resp.json()["analysis_id"]


def _start_zip(client, files: dict[str, bytes]) -> str:
    resp = client.post(
        "/api/repositories/upload",
        files={"file": ("demo.zip", make_zip(files), "application/zip")},
    )
    assert resp.status_code == 202
    return resp.json()["analysis_id"]


def test_github_analysis_reaches_completion(client):
    analysis_id = _start_github(client)
    body = client.get(f"/api/analysis/{analysis_id}").json()
    assert body["status"] == "completed"
    assert body["repository"]["name"] == "example-project"
    assert body["summary"]["files_analyzed"] >= 1


def test_zip_analysis_reaches_completion(client):
    analysis_id = _start_zip(
        client,
        {
            "README.md": b"# demo\n",
            "package.json": b'{"name":"demo"}\n',
            "src/main.py": b"print('hi')\n",
        },
    )
    body = client.get(f"/api/analysis/{analysis_id}").json()
    assert body["status"] == "completed"
    assert body["summary"]["files_analyzed"] == 3


def test_result_endpoints_available_after_completion(client):
    analysis_id = _start_zip(client, {"README.md": b"# demo\n"})
    for suffix in ["architecture", "findings", "roadmap", "report"]:
        resp = client.get(f"/api/analysis/{analysis_id}/{suffix}")
        assert resp.status_code == 200, suffix


def test_result_endpoints_conflict_before_completion_is_not_possible_here(client):
    # Under TestClient the pipeline finishes before we can observe queued state;
    # this just documents that a missing analysis still 404s.
    resp = client.get("/api/analysis/analysis_missing/findings")
    assert resp.status_code == 404


def test_unsafe_archive_fails_analysis_with_code(client):
    data = make_zip({"ok.txt": b"fine", "../evil.txt": b"pwned"})
    resp = client.post(
        "/api/repositories/upload",
        files={"file": ("evil.zip", data, "application/zip")},
    )
    assert resp.status_code == 202
    analysis_id = resp.json()["analysis_id"]

    status = client.get(f"/api/analysis/{analysis_id}").json()
    assert status["status"] == "failed"
    assert status["error"]["code"] == "UNSAFE_ARCHIVE_ENTRY"

    # Result endpoints report the failure clearly.
    findings = client.get(f"/api/analysis/{analysis_id}/findings")
    assert findings.status_code == 409
    assert findings.json()["error"]["code"] == "UNSAFE_ARCHIVE_ENTRY"


def test_delete_analysis(client):
    analysis_id = _start_zip(client, {"README.md": b"# demo\n"})
    assert client.delete(f"/api/analysis/{analysis_id}").json()["deleted"] is True
    assert client.delete(f"/api/analysis/{analysis_id}").status_code == 404


def test_missing_analysis_returns_404(client):
    resp = client.get("/api/analysis/analysis_does_not_exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


def test_chat_returns_structured_response(client):
    analysis_id = _start_zip(client, {"README.md": b"# demo\n"})
    resp = client.post(
        f"/api/analysis/{analysis_id}/chat",
        json={"question": "What does this project do?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Grounded answering lands in phase 4; until then we answer honestly.
    assert body["insufficient_evidence"] is True
    assert body["citations"] == []
