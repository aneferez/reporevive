from __future__ import annotations

import io
import zipfile

import pytest

from app.api.errors import AppError
from app.intake.github import parse_github_url


@pytest.mark.parametrize(
    "url,owner,repo",
    [
        ("https://github.com/example/example-project", "example", "example-project"),
        ("github.com/octocat/Hello-World", "octocat", "Hello-World"),
        ("https://github.com/example/example-project.git", "example", "example-project"),
        ("https://www.github.com/a/b/tree/main/src", "a", "b"),
    ],
)
def test_parse_valid_github_urls(url, owner, repo):
    ref = parse_github_url(url)
    assert ref.owner == owner
    assert ref.repo == repo
    assert ref.canonical_url == f"https://github.com/{owner}/{repo}"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "https://gitlab.com/example/project",
        "https://github.com/only-owner",
        "https://example.com/github.com/a/b",
        "ftp://github.com/a/b",
        "https://github.com/features/actions",  # reserved site path
    ],
)
def test_parse_invalid_github_urls(url):
    with pytest.raises(AppError):
        parse_github_url(url)


def test_analyze_endpoint_accepts_valid_url(client):
    resp = client.post(
        "/api/repositories/analyze",
        json={"repository_url": "https://github.com/example/example-project"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["repository"]["name"] == "example-project"
    assert body["repository"]["source_type"] == "github"
    assert body["analysis_id"].startswith("analysis_")


def test_analyze_endpoint_rejects_bad_url(client):
    resp = client.post(
        "/api/repositories/analyze",
        json={"repository_url": "https://gitlab.com/example/project"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REPOSITORY_URL"


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("README.md", "# demo\n")
    return buf.getvalue()


def test_upload_accepts_zip(client):
    resp = client.post(
        "/api/repositories/upload",
        files={"file": ("demo.zip", _zip_bytes(), "application/zip")},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["repository"]["source_type"] == "zip"
    assert body["repository"]["name"] == "demo"


def test_upload_rejects_non_zip(client):
    resp = client.post(
        "/api/repositories/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ARCHIVE"
