"""Analysis pipeline orchestration.

Runs as a background task after the intake endpoint returns. Each stage updates
the record's ``stage``/``progress`` so the frontend can poll the status
endpoint. Deterministic analyzers and the AI layer are added in later phases;
this module owns the ordering, timing, and failure handling around them.

Safety: this pipeline never executes repository code. It only reads redacted
text that intake has already vetted and size-limited.
"""

from __future__ import annotations

import logging

from ..config import Settings, get_settings
from ..models.enums import AnalysisStatus, Stage
from .exceptions import PipelineError
from .records import AnalysisRecord
from .store import AnalysisStore

logger = logging.getLogger("reporevive.pipeline")


def _advance(record: AnalysisRecord, stage: Stage, progress: int) -> None:
    record.stage = stage
    record.progress = progress


def run_analysis(store: AnalysisStore, analysis_id: str) -> None:
    """Execute the full analysis for a queued record.

    Designed to be scheduled via ``BackgroundTasks`` so it runs in a worker
    thread and never blocks the event loop.
    """

    record = store.get(analysis_id)
    if record is None:
        logger.warning("Analysis %s vanished before pipeline start", analysis_id)
        return

    settings = get_settings()
    from .records import utcnow

    record.status = AnalysisStatus.running
    record.started_at = utcnow()
    logger.info("Analysis %s started (%s)", analysis_id, record.source_type.value)

    try:
        _run_stages(record, settings)
        record.status = AnalysisStatus.completed
        record.stage = Stage.complete
        record.progress = 100
        record.completed_at = utcnow()
        logger.info(
            "Analysis %s completed: %d files, %d findings (%dms)",
            analysis_id,
            record.files_analyzed,
            len(record.findings),
            record.duration_ms,
        )
    except PipelineError as exc:
        record.status = AnalysisStatus.failed
        record.stage = Stage.failed
        record.completed_at = utcnow()
        record.error_code = exc.code
        record.error_message = exc.message
        logger.warning("Analysis %s failed: %s (%s)", analysis_id, exc.message, exc.code)
    except Exception as exc:  # noqa: BLE001 - convert to safe failure state
        record.status = AnalysisStatus.failed
        record.stage = Stage.failed
        record.completed_at = utcnow()
        record.error_code = "INTERNAL_ERROR"
        record.error_message = "Analysis failed unexpectedly."
        logger.exception("Analysis %s crashed: %s", analysis_id, exc)


def _run_stages(record: AnalysisRecord, settings: Settings) -> None:
    """Ordered analysis stages.

    Phase 1 wires the stage transitions and produces a valid empty result set.
    Later phases replace each ``# TODO(phase-N)`` block with real logic while
    keeping this ordering intact.
    """

    _advance(record, Stage.validating, 5)
    # Intake already validated the source in the request handler.

    _advance(record, Stage.intake, 15)
    from ..intake.service import run_intake

    intake = run_intake(record, settings)
    record.files = intake.files
    record.secret_hits = intake.secret_hits
    record.notes.extend(intake.notes)
    # Free the uploaded archive bytes now that files are extracted.
    record.archive_bytes = None

    _advance(record, Stage.inspecting, 30)
    record.files_analyzed = len(record.files)
    if not record.files:
        record.notes.append("No supported source files were found to inspect.")

    # Import analyzers lazily so app startup stays light.
    from ..analyzers.api_contract import analyze_api_contract
    from ..analyzers.architecture import build_architecture
    from ..analyzers.config_inspect import inspect_configuration
    from ..analyzers.context import AnalysisContext
    from ..analyzers.roadmap import build_roadmap
    from ..analyzers.runner import (
        build_overview,
        compute_readiness,
        default_limitations,
        finalize_findings,
    )
    from ..analyzers.secrets import secret_findings
    from ..analyzers.stack import detect_stack
    from ..analyzers.testing_docs import assess_testing_docs

    ctx = AnalysisContext.build(record.files)
    findings = []

    _advance(record, Stage.stack, 45)
    stack_result = detect_stack(ctx)
    record.stack = stack_result.stack
    findings.extend(stack_result.findings)

    _advance(record, Stage.config, 55)
    findings.extend(inspect_configuration(ctx))

    _advance(record, Stage.api, 65)
    api_result = analyze_api_contract(ctx)
    findings.extend(api_result.findings)

    _advance(record, Stage.secrets, 75)
    findings.extend(secret_findings(record.secret_hits))
    findings.extend(assess_testing_docs(ctx))

    _advance(record, Stage.report, 98)
    record.findings = finalize_findings(findings)
    record.architecture = build_architecture(stack_result, api_result, ctx)
    record.roadmap = build_roadmap(record.findings)
    record.readiness_label = compute_readiness(record.findings)
    record.overview = build_overview(
        record.files_analyzed, record.stack, record.findings, truncated=_was_truncated(record)
    )
    record.limitations = default_limitations()

    _advance(record, Stage.ai, 99)
    # Build the retrieval index for grounded chat, and (optionally) enrich the
    # overview with AI narration. Neither step may fail the analysis.
    _build_retrieval_and_narration(record, settings)


def _build_retrieval_and_narration(record: AnalysisRecord, settings: Settings) -> None:
    try:
        from ..retrieval.lexical import LexicalIndex

        record.retrieval_index = LexicalIndex.build(record.files)
    except Exception as exc:  # noqa: BLE001 - retrieval is best-effort
        logger.warning("Retrieval index build failed for %s: %s", record.analysis_id, exc)

    if settings.ai_enabled:
        try:
            from ..ai.narration import generate_overview

            narrated = generate_overview(record, settings)
            if narrated:
                record.overview = narrated
        except Exception as exc:  # noqa: BLE001 - narration is best-effort
            logger.info("AI narration skipped for %s: %s", record.analysis_id, exc)


def _was_truncated(record: AnalysisRecord) -> bool:
    return any("truncated" in note.lower() for note in record.notes)
