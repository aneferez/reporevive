"""Helpers for building in-memory archives in tests."""

from __future__ import annotations

import io
import stat
import tarfile
import time
import zipfile

from app.analyzers.context import AnalysisContext
from app.core.records import RepoFile
from app.intake.filetree import classify_language


def make_zip(
    files: dict[str, bytes],
    *,
    symlinks: dict[str, str] | None = None,
    root: str | None = None,
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            arcname = f"{root}/{name}" if root else name
            zf.writestr(arcname, content)
        for name, target in (symlinks or {}).items():
            arcname = f"{root}/{name}" if root else name
            info = zipfile.ZipInfo(arcname)
            info.create_system = 3  # unix
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, target)
    return buf.getvalue()


def make_files(files: dict[str, str]) -> list[RepoFile]:
    return [
        RepoFile(
            path=path,
            content=content,
            size_bytes=len(content.encode("utf-8")),
            language=classify_language(path),
        )
        for path, content in files.items()
    ]


def make_ctx(files: dict[str, str]) -> AnalysisContext:
    return AnalysisContext.build(make_files(files))


def make_tar_gz(files: dict[str, bytes], *, root: str = "repo-main") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in files.items():
            info = tarfile.TarInfo(name=f"{root}/{name}")
            info.size = len(content)
            info.mtime = int(time.time())
            tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()
