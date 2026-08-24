"""Architecture summary (FR-04).

Builds a component/connection graph from detected stack evidence. Components are
only added when there is evidence; relationships are only drawn when both ends
exist. Nothing is asserted as fact without a supporting file.
"""

from __future__ import annotations

from ..models.schemas import (
    ArchitectureComponent,
    ArchitectureConnection,
    ArchitectureResponse,
)
from .api_contract import ApiResult
from .context import AnalysisContext
from .stack import StackResult

_DEPLOY_FILES = (
    "dockerfile", "docker-compose.yml", "render.yaml", "procfile",
    "vercel.json", "netlify.toml", "fly.toml",
)


def build_architecture(
    stack: StackResult, api: ApiResult, ctx: AnalysisContext
) -> ArchitectureResponse:
    components: list[ArchitectureComponent] = []
    connections: list[ArchitectureConnection] = []

    has_frontend = bool(stack.stack.frontend)
    has_backend = bool(stack.stack.backend)
    has_db = bool(stack.stack.database)

    if has_frontend:
        components.append(
            ArchitectureComponent(
                id="frontend",
                type="frontend",
                label=" + ".join(stack.stack.frontend[:3]) or "Frontend",
                evidence_files=stack.frontend_evidence[:5],
            )
        )
    if has_backend:
        components.append(
            ArchitectureComponent(
                id="backend",
                type="backend",
                label=" + ".join(stack.stack.backend[:3]) or "Backend",
                evidence_files=stack.backend_evidence[:5],
            )
        )
    if has_db:
        components.append(
            ArchitectureComponent(
                id="database",
                # PRD section 9 taxonomy uses "persistence" (matches the frontend);
                # the node id stays "database" so connection targets still resolve.
                type="persistence",
                label=" + ".join(stack.stack.database[:3]),
                evidence_files=stack.database_evidence[:5],
            )
        )

    deploy_evidence = [f.path for f in ctx.files if ctx.basename(f.path).lower() in _DEPLOY_FILES]
    if deploy_evidence:
        components.append(
            ArchitectureComponent(
                id="deployment",
                type="deployment",
                label="Deployment config",
                evidence_files=deploy_evidence[:5],
            )
        )

    if has_frontend and has_backend:
        connections.append(
            ArchitectureConnection(
                source="frontend",
                target="backend",
                label="HTTP API" if api.frontend_calls else "HTTP API (inferred)",
                evidence_files=[],
            )
        )
    if has_backend and has_db:
        connections.append(
            ArchitectureConnection(
                source="backend",
                target="database",
                label="Database connection",
                evidence_files=stack.database_evidence[:3],
            )
        )

    return ArchitectureResponse(components=components, connections=connections)
