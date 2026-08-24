from __future__ import annotations

import httpx
import pytest

from app.core.exceptions import PipelineError
from app.intake.github import GitHubRepoRef, _raise_for_github_status

REF = GitHubRepoRef(owner="octocat", repo="Hello-World")


def test_404_maps_to_not_found():
    with pytest.raises(PipelineError) as exc:
        _raise_for_github_status(httpx.Response(404), REF)
    assert exc.value.code == "REPOSITORY_NOT_FOUND"


def test_rate_limited_maps_to_rate_limited():
    resp = httpx.Response(403, headers={"X-RateLimit-Remaining": "0"})
    with pytest.raises(PipelineError) as exc:
        _raise_for_github_status(resp, REF)
    assert exc.value.code == "RATE_LIMITED"


def test_forbidden_maps_to_private_unsupported():
    with pytest.raises(PipelineError) as exc:
        _raise_for_github_status(httpx.Response(403), REF)
    assert exc.value.code == "PRIVATE_REPOSITORY_UNSUPPORTED"


def test_200_passes():
    # Should not raise.
    _raise_for_github_status(httpx.Response(200), REF)


def test_allowed_download_hosts():
    from app.intake.github import _is_allowed_download_host

    assert _is_allowed_download_host("codeload.github.com")
    assert _is_allowed_download_host("api.github.com")
    assert _is_allowed_download_host("objects.githubusercontent.com")
    assert not _is_allowed_download_host("evil.example.com")
    assert not _is_allowed_download_host("github.com.evil.com")
    assert not _is_allowed_download_host("")
