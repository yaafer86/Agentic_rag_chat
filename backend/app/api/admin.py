"""Admin router — global admin only. Users, workspaces, audit log, provider status."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select

from app.core.rbac import DB, GlobalAdmin, require_global_admin
from app.models.db import AuditLog, User, Workspace
from app.models.schemas import AuditLogOut, WorkspaceOut

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_global_admin)],
)


@router.get("/users")
async def list_users(
    _admin: GlobalAdmin,
    db: DB,
    active_only: bool = Query(default=False),
) -> list[dict[str, Any]]:
    stmt = select(User)
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
    users = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "is_global_admin": u.is_global_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.put("/users/{user_id}/active")
async def set_user_active(
    user_id: str,
    active: bool,
    admin: GlobalAdmin,
    db: DB,
) -> dict[str, Any]:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    u.is_active = active
    db.add(
        AuditLog(
            workspace_id=None,
            user_id=admin.id,
            action="admin.user.set_active",
            target_type="user",
            target_id=user_id,
            payload={"active": active},
        )
    )
    await db.commit()
    return {"id": u.id, "is_active": u.is_active}


@router.put("/users/{user_id}/global-admin")
async def set_global_admin(
    user_id: str,
    value: bool,
    admin: GlobalAdmin,
    db: DB,
) -> dict[str, Any]:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    u.is_global_admin = value
    db.add(
        AuditLog(
            workspace_id=None,
            user_id=admin.id,
            action="admin.user.set_global_admin",
            target_type="user",
            target_id=user_id,
            payload={"value": value},
        )
    )
    await db.commit()
    return {"id": u.id, "is_global_admin": u.is_global_admin}


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_all_workspaces(_admin: GlobalAdmin, db: DB) -> list[Workspace]:
    return list((await db.execute(select(Workspace))).scalars().all())


@router.get("/audit", response_model=list[AuditLogOut])
async def audit_log(
    _admin: GlobalAdmin,
    db: DB,
    workspace_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at))
    if workspace_id:
        stmt = stmt.where(AuditLog.workspace_id == workspace_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars()
    return list(rows.all())


@router.get("/providers")
async def provider_status(_admin: GlobalAdmin) -> dict[str, Any]:
    """Ping configured data services and LLM endpoints. Live probes, cache-free."""
    from app.services import minio as minio_svc
    from app.services import neo4j as neo4j_svc
    from app.services import qdrant as qdrant_svc

    return {
        "qdrant": await qdrant_svc.healthcheck(),
        "neo4j": await neo4j_svc.healthcheck(),
        "minio": await minio_svc.healthcheck(),
    }
