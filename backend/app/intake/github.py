"""Public GitHub URL validation (FR-01) and normalization.

Only well-formed ``github.com/{owner}/{repo}`` URLs are accepted. This is the
first line of SSRF defense: the backend never fetches arbitrary user-supplied
hosts (PRD section 16). Actual content fetching is added in phase 2.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from ..api.errors import AppError, ErrorCode
from ..config import Settings
from ..core.exceptions import PipelineError

logger = logging.getLogger("reporevive.github")

# GitHub owner/repo naming: letters, digits, hyphen, underscore, dot.
_SEGMENT = r"[A-Za-z0-9_.-]+"
_ALLOWED_HOSTS = {"github.com", "www.github.com"}
# Reserved GitHub paths that are not repositories.
_RESERVED_OWNERS = {
    "features",
    "topics",
    "collections",
    "sponsors",
    "marketplace",
    "explore",
    "settings",
    "notifications",
    "about",
    "pricing",
    "login",
    "join",
}


@dataclass(frozen=True)
class GitHubRepoRef:
    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


def parse_github_url(raw_url: str) -> GitHubRepoRef:
    """Validate and normalize a public GitHub repository URL.

    Raises ``AppError`` with ``INVALID_REPOSITORY_URL`` on anything that is not
    a plausible public repository URL.
    """

    if not raw_url or not raw_url.strip():
        raise AppError(
            ErrorCode.INVALID_REPOSITORY_URL,
            "Enter a valid public GitHub repository URL.",
        )

    url = raw_url.strip()
    # Accept bare "github.com/owner/repo" by assuming https.
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise AppError(
            ErrorCode.INVALID_REPOSITORY_URL,
            "Only http(s) GitHub URLs are supported.",
        )

    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise AppError(
            ErrorCode.INVALID_REPOSITORY_URL,
            "Only public github.com repository URLs are supported.",
        )

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise AppError(
            ErrorCode.INVALID_REPOSITORY_URL,
            "URL must point to a repository: github.com/{owner}/{repository}.",
        )

    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not re.fullmatch(_SEGMENT, owner) or not re.fullmatch(_SEGMENT, repo):
        raise AppError(
            ErrorCode.INVALID_REPOSITORY_URL,
            "The repository owner or name contains unsupported characters.",
        )

    if owner.lower() in _RESERVED_OWNERS:
        raise AppError(
            ErrorCode.INVALID_REPOSITORY_URL,
            "That URL is a GitHub site path, not a repository.",
        )

    return GitHubRepoRef(owner=owner, repo=repo)


def _is_allowed_download_host(host: str) -> bool:
    host = (host or "").lower()
    if host in {"api.github.com", "codeload.github.com", "github.com", "www.github.com"}:
        return True
    # GitHub serves archive blobs from *.githubusercontent.com.
    return host.endswith(".githubusercontent.com")


def fetch_repo_tarball(ref: GitHubRepoRef, settings: Settings) -> bytes:
    """Download a public repository's default-branch tarball, safely.

    Only ``api.github.com`` is contacted, redirects are bounded and their final
    host is validated (SSRF guard), and the body is streamed with a hard byte
    cap so an oversized response can't exhaust memory. Raises ``PipelineError``
    with a structured code on any failure.
    """

    url = f"https://api.github.com/repos/{ref.owner}/{ref.repo}/tarball"
    headers = {
        "User-Agent": "RepoRevive",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    max_bytes = settings.max_extracted_bytes
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=settings.github_request_timeout_s,
            max_redirects=5,
        ) as client:
            with client.stream("GET", url, headers=headers) as resp:
                # Validate the final host after any redirects.
                if not _is_allowed_download_host(resp.url.host or ""):
                    raise PipelineError(
                        ErrorCode.REPOSITORY_NOT_FOUND,
                        "The repository download redirected to an unexpected host.",
                    )
                if resp.status_code != 200:
                    resp.read()  # load the (small) error body for status handling
                    _raise_for_github_status(resp, ref)

                ctype = resp.headers.get("content-type", "").lower()
                if "html" in ctype:
                    raise PipelineError(
                        ErrorCode.REPOSITORY_NOT_FOUND,
                        "Unexpected response while fetching the repository.",
                    )

                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise PipelineError(
                            ErrorCode.REPOSITORY_TOO_LARGE,
                            "The repository archive is too large to analyze.",
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
    except httpx.HTTPError as exc:
        logger.warning("GitHub fetch failed for %s: %s", ref.full_name, exc)
        raise PipelineError(
            ErrorCode.REPOSITORY_NOT_FOUND,
            "Could not reach the repository. Check the URL and try again.",
        ) from exc


def _raise_for_github_status(resp: httpx.Response, ref: GitHubRepoRef) -> None:
    if resp.status_code == 200:
        return
    if resp.status_code == 404:
        raise PipelineError(
            ErrorCode.REPOSITORY_NOT_FOUND,
            "Repository not found. It may be private or misspelled; only public "
            "repositories are supported.",
        )
    if resp.status_code in (403, 429):
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining == "0" or "rate limit" in resp.text.lower():
            raise PipelineError(
                ErrorCode.RATE_LIMITED,
                "GitHub rate limit reached. Try again later or configure a token.",
            )
        raise PipelineError(
            ErrorCode.PRIVATE_REPOSITORY_UNSUPPORTED,
            "Access to this repository is forbidden; only public repositories "
            "are supported.",
        )
    raise PipelineError(
        ErrorCode.REPOSITORY_NOT_FOUND,
        f"Unexpected response while fetching the repository ({resp.status_code}).",
    )
