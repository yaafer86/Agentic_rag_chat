"""Dashboard CRUD. Export is produced by the sandbox service on demand."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.rbac import DB, CurrentUser, CurrentWorkspace, require_role
from app.models.db import AuditLog, Dashboard, Role
from app.models.schemas import DashboardCreate, DashboardOut

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


@router.post(
    "",
    response_model=DashboardOut,
    status_code=201,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value, Role.WORKSPACE_EDITOR.value))],
)
async def create_dashboard(
    body: DashboardCreate,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> Dashboard:
    ws, _ = ctx
    d = Dashboard(
        workspace_id=ws.id,
        name=body.name,
        layout=body.layout,
        global_filters=body.global_filters,
        created_by=user.id,
    )
    db.add(d)
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="dashboard.create",
            target_type="dashboard",
            target_id=d.id,
            payload={"name": body.name},
        )
    )
    await db.commit()
    await db.refresh(d)
    return d


@router.get("", response_model=list[DashboardOut])
async def list_dashboards(ctx: CurrentWorkspace, db: DB) -> list[Dashboard]:
    ws, _ = ctx
    rows = (await db.execute(select(Dashboard).where(Dashboard.workspace_id == ws.id))).scalars()
    return list(rows.all())


@router.get("/{dashboard_id}", response_model=DashboardOut)
async def get_dashboard(
    dashboard_id: str, ctx: CurrentWorkspace, db: DB
) -> Dashboard:
    ws, _ = ctx
    d = (
        await db.execute(
            select(Dashboard).where(
                Dashboard.id == dashboard_id, Dashboard.workspace_id == ws.id
            )
        )
    ).scalar_one_or_none()
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dashboard not found")
    return d


@router.put(
    "/{dashboard_id}",
    response_model=DashboardOut,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value, Role.WORKSPACE_EDITOR.value))],
)
async def update_dashboard(
    dashboard_id: str,
    body: DashboardCreate,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> Dashboard:
    ws, _ = ctx
    d = (
        await db.execute(
            select(Dashboard).where(
                Dashboard.id == dashboard_id, Dashboard.workspace_id == ws.id
            )
        )
    ).scalar_one_or_none()
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dashboard not found")
    d.name = body.name
    d.layout = body.layout
    d.global_filters = body.global_filters
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="dashboard.update",
            target_type="dashboard",
            target_id=d.id,
            payload={"name": d.name},
        )
    )
    await db.commit()
    await db.refresh(d)
    return d


@router.delete(
    "/{dashboard_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value))],
)
async def delete_dashboard(
    dashboard_id: str, ctx: CurrentWorkspace, user: CurrentUser, db: DB
) -> None:
    ws, _ = ctx
    d = (
        await db.execute(
            select(Dashboard).where(
                Dashboard.id == dashboard_id, Dashboard.workspace_id == ws.id
            )
        )
    ).scalar_one_or_none()
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dashboard not found")
    await db.delete(d)
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="dashboard.delete",
            target_type="dashboard",
            target_id=dashboard_id,
            payload={},
        )
    )
    await db.commit()
