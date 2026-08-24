"""Intake dispatch: turn a queued record's source into redacted RepoFiles."""

from __future__ import annotations

from ..api.errors import ErrorCode
from ..config import Settings
from ..core.exceptions import PipelineError
from ..core.records import AnalysisRecord
from ..models.enums import SourceType
from .archive import extract_tar_gz, extract_zip
from .base import IntakeResult
from .github import GitHubRepoRef, fetch_repo_tarball


def run_intake(record: AnalysisRecord, settings: Settings) -> IntakeResult:
    if record.source_type == SourceType.zip:
        if not record.archive_bytes:
            raise PipelineError(
                ErrorCode.INVALID_ARCHIVE, "No uploaded archive data is available."
            )
        return extract_zip(record.archive_bytes, settings)

    # GitHub source.
    if not record.github_owner or not record.github_repo:
        raise PipelineError(
            ErrorCode.INVALID_REPOSITORY_URL, "Repository reference is missing."
        )
    ref = GitHubRepoRef(owner=record.github_owner, repo=record.github_repo)
    data = fetch_repo_tarball(ref, settings)
    return extract_tar_gz(data, settings)
