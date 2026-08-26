"""Safe archive extraction for ZIP uploads and GitHub tarballs (FR-02).

Everything is extracted **in memory** — nothing is written to disk — so archive
path traversal cannot touch the filesystem. We still detect and reject unsafe
entries, skip symlinks, and enforce every size/count limit from PRD section 7.
Repository code is never executed.
"""

from __future__ import annotations

import io
import stat
import tarfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

from ..api.errors import ErrorCode
from ..config import Settings
from ..core.exceptions import PipelineError
from ..core.records import RepoFile
from ..security.redaction import redact_text
from .base import IntakeResult
from .filetree import (
    classify_language,
    is_ignored,
    is_text_candidate,
    looks_binary,
    normalize_path,
)


@dataclass
class _RawEntry:
    name: str
    size: int | None
    is_symlink: bool
    reader: Callable[[int], bytes]  # read up to n bytes, lazily


def extract_zip(data: bytes, settings: Settings) -> IntakeResult:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PipelineError(
            ErrorCode.INVALID_ARCHIVE, "The uploaded file is not a valid ZIP archive."
        ) from exc

    with zf:
        infos = zf.infolist()
        _validate_entry_count(len(infos), settings)
        entries: list[_RawEntry] = []
        for info in infos:
            if info.is_dir():
                continue
            entries.append(
                _RawEntry(
                    name=info.filename,
                    size=info.file_size,
                    is_symlink=_zip_is_symlink(info),
                    reader=_zip_reader(zf, info),
                )
            )
        return _ingest(entries, settings)


def extract_tar_gz(data: bytes, settings: Settings) -> IntakeResult:
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except tarfile.TarError as exc:
        raise PipelineError(
            ErrorCode.INVALID_ARCHIVE, "The repository archive could not be read."
        ) from exc

    with tf:
        members = tf.getmembers()
        _validate_entry_count(len(members), settings)
        entries = []
        for member in members:
            if member.isdir():
                continue
            is_symlink = member.issym() or member.islnk()
            if not (member.isfile() or is_symlink):
                continue  # skip devices, fifos, etc.
            entries.append(
                _RawEntry(
                    name=member.name,
                    size=member.size,
                    is_symlink=is_symlink,
                    reader=_tar_reader(tf, member),
                )
            )
        return _ingest(entries, settings)


# ---------------------------------------------------------------------------
# Shared ingestion
# ---------------------------------------------------------------------------


def _validate_entry_count(count: int, settings: Settings) -> None:
    if count > settings.max_archive_entries:
        raise PipelineError(
            ErrorCode.ARCHIVE_TOO_LARGE,
            "The archive contains too many entries and was rejected.",
        )


def _ingest(entries: list[_RawEntry], settings: Settings) -> IntakeResult:
    root = _common_root([e.name for e in entries])
    result = IntakeResult()
    total_bytes = 0

    for entry in entries:
        if entry.is_symlink:
            result.notes.append(f"Skipped symlink entry: {entry.name}")
            continue

        rel = _strip_root(entry.name, root)
        if not rel.strip():
            continue  # the root directory entry itself

        norm = normalize_path(rel)
        if norm is None:
            raise PipelineError(
                ErrorCode.UNSAFE_ARCHIVE_ENTRY,
                "The archive contains an unsafe path entry and was rejected.",
            )

        if is_ignored(norm) or not is_text_candidate(norm):
            continue

        if entry.size is not None and entry.size > settings.max_file_bytes:
            result.notes.append(f"Skipped large file (> limit): {norm}")
            continue

        raw = entry.reader(settings.max_file_bytes + 1)
        if len(raw) > settings.max_file_bytes:
            result.notes.append(f"Skipped large file (> limit): {norm}")
            continue

        total_bytes += len(raw)
        if total_bytes > settings.max_extracted_bytes:
            raise PipelineError(
                ErrorCode.ARCHIVE_TOO_LARGE,
                "The archive exceeds the extracted-size limit and was rejected.",
            )

        if looks_binary(raw):
            continue

        text = raw.decode("utf-8", errors="replace")
        redacted, hits = redact_text(text)
        for hit in hits:
            hit.file = norm
        result.secret_hits.extend(hits)
        result.files.append(
            RepoFile(
                path=norm,
                content=redacted,
                size_bytes=len(raw),
                language=classify_language(norm),
            )
        )

        if len(result.files) >= settings.max_analyzed_files:
            result.truncated = True
            break

    if result.truncated:
        result.notes.append(
            f"Reached the {settings.max_analyzed_files}-file inspection limit; "
            "analysis truncated."
        )
    return result


def _zip_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _zip_reader(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> Callable[[int], bytes]:
    def read(n: int) -> bytes:
        with zf.open(info) as fh:
            return fh.read(n)

    return read


def _tar_reader(tf: tarfile.TarFile, member: tarfile.TarInfo) -> Callable[[int], bytes]:
    def read(n: int) -> bytes:
        fh = tf.extractfile(member)
        if fh is None:
            return b""
        try:
            return fh.read(n)
        finally:
            fh.close()

    return read


def _common_root(names: list[str]) -> str | None:
    """The single shared top-level directory, if all entries are nested under one.

    GitHub tarballs wrap everything in ``owner-repo-sha/``; many user zips wrap
    everything in a single project folder. Stripping it yields clean repo paths.

    Returns ``None`` unless *every* entry is at least two segments deep and
    shares the same first segment — otherwise a top-level file (or differing
    prefixes) means there is no strippable root.
    """

    first: str | None = None
    for name in names:
        cleaned = name.replace("\\", "/").strip()
        if cleaned.startswith("./"):
            cleaned = cleaned[2:]
        parts = [p for p in cleaned.split("/") if p not in ("", ".")]
        if len(parts) < 2:
            return None  # a top-level file exists; nothing to strip
        if first is None:
            first = parts[0]
        elif parts[0] != first:
            return None
    return first


def _strip_root(name: str, root: str | None) -> str:
    cleaned = name.replace("\\", "/").strip()
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if root:
        if cleaned == root:
            return ""
        prefix = root + "/"
        if cleaned.startswith(prefix):
            return cleaned[len(prefix):]
    return cleaned
