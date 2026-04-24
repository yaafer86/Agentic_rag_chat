"""Sandbox router."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.rbac import CurrentUser, CurrentWorkspace, require_role
from app.models.db import Role
from app.models.schemas import SandboxArtifact, SandboxRunRequest, SandboxRunResponse
from app.services import sandbox as sbx

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.post(
    "/run",
    response_model=SandboxRunResponse,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value, Role.WORKSPACE_EDITOR.value))],
)
async def run_code(
    body: SandboxRunRequest,
    _ctx: CurrentWorkspace,
    _user: CurrentUser,
) -> SandboxRunResponse:
    try:
        result = await sbx.run(
            body.code,
            files=body.files,
            timeout_s=body.timeout_s,
            memory_mb=body.memory_mb,
        )
    except sbx.SandboxUnavailable as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"sandbox unavailable: {e}",
        ) from e

    return SandboxRunResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        plots=[base64.b64encode(p).decode("ascii") for p in result.plots],
        artifacts=[
            SandboxArtifact(
                name=a.name,
                mime=a.mime,
                base64=base64.b64encode(a.data).decode("ascii"),
            )
            for a in result.artifacts
        ],
        duration_ms=result.duration_ms,
    )
