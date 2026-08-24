"""Runs sample repositories through the real analysis pipeline in-process."""

from __future__ import annotations

import io
import uuid
import zipfile

from app.core.pipeline import run_analysis
from app.core.records import AnalysisRecord
from app.core.store import AnalysisStore
from app.models.enums import SourceType
from app.models.schemas import RepositoryInfo


def zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def run_repo(name: str, files: dict[str, str]) -> AnalysisRecord:
    """Run a files dict through intake + analyzers, returning the final record."""

    store = AnalysisStore(max_items=10)
    record = AnalysisRecord(
        analysis_id=f"analysis_{uuid.uuid4().hex[:8]}",
        repository=RepositoryInfo(name=name, source_type=SourceType.zip),
        source_type=SourceType.zip,
        archive_bytes=zip_bytes(files),
    )
    store.create(record)
    run_analysis(store, record.analysis_id)
    return record
