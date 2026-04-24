"""Workspace CRUD, members, folders, ACL, model prefs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.rbac import (
    DB,
    CurrentUser,
    CurrentWorkspace,
    require_global_admin,
    require_role,
)
from app.models.db import (
    AuditLog,
    Folder,
    Role,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.schemas import (
    FolderCreate,
    FolderOut,
    MemberAdd,
    MemberOut,
    ModelPrefs,
    WorkspaceCreate,
    WorkspaceOut,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    user: CurrentUser,
    db: DB,
) -> Workspace:
    ws = Workspace(name=body.name, slug=body.slug, description=body.description)
    db.add(ws)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already in use") from None
    db.add(
        WorkspaceMember(
            workspace_id=ws.id,
            user_id=user.id,
            role=Role.WORKSPACE_ADMIN.value,
        )
    )
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="workspace.create",
            target_type="workspace",
            target_id=ws.id,
            payload={"name": ws.name, "slug": ws.slug},
        )
    )
    await db.commit()
    await db.refresh(ws)
    return ws


@router.get("", response_model=list[WorkspaceOut])
async def list_my_workspaces(user: CurrentUser, db: DB) -> list[Workspace]:
    if user.is_global_admin:
        return list((await db.execute(select(Workspace))).scalars().all())
    rows = (
        await db.execute(
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user.id)
        )
    ).scalars()
    return list(rows.all())


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(ctx: CurrentWorkspace) -> Workspace:
    return ctx[0]


@router.put(
    "/{workspace_id}/model-prefs",
    response_model=WorkspaceOut,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value))],
)
async def set_model_prefs(
    workspace_id: str,
    prefs: ModelPrefs,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> Workspace:
    ws, _ = ctx
    ws.model_prefs = prefs.model_dump(exclude_none=True)
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="workspace.set_model_prefs",
            target_type="workspace",
            target_id=ws.id,
            payload=ws.model_prefs,
        )
    )
    await db.commit()
    await db.refresh(ws)
    return ws


# ---------- Members ----------


@router.post(
    "/{workspace_id}/members",
    response_model=MemberOut,
    status_code=201,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value))],
)
async def add_member(
    workspace_id: str,
    body: MemberAdd,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> WorkspaceMember:
    ws, _ = ctx
    target = (await db.execute(select(User).where(User.id == body.user_id))).scalar_one_or_none()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    m = WorkspaceMember(workspace_id=ws.id, user_id=body.user_id, role=body.role)
    db.add(m)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "user is already a member") from None
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="member.add",
            target_type="user",
            target_id=body.user_id,
            payload={"role": body.role},
        )
    )
    await db.commit()
    await db.refresh(m)
    return m


@router.get(
    "/{workspace_id}/members",
    response_model=list[MemberOut],
)
async def list_members(
    workspace_id: str,
    ctx: CurrentWorkspace,
    db: DB,
) -> list[WorkspaceMember]:
    rows = (
        await db.execute(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == ctx[0].id)
        )
    ).scalars()
    return list(rows.all())


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value))],
)
async def remove_member(
    workspace_id: str,
    user_id: str,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> None:
    ws, _ = ctx
    m = (
        await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws.id, WorkspaceMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    await db.delete(m)
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="member.remove",
            target_type="user",
            target_id=user_id,
            payload={},
        )
    )
    await db.commit()


# ---------- Folders ----------


@router.post(
    "/{workspace_id}/folders",
    response_model=FolderOut,
    status_code=201,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value, Role.WORKSPACE_EDITOR.value))],
)
async def create_folder(
    workspace_id: str,
    body: FolderCreate,
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> Folder:
    ws, _ = ctx
    folder = Folder(workspace_id=ws.id, path=body.path.strip("/"), acl=body.acl)
    db.add(folder)
    db.add(
        AuditLog(
            workspace_id=ws.id,
            user_id=user.id,
            action="folder.create",
            target_type="folder",
            target_id=folder.id,
            payload={"path": folder.path},
        )
    )
    await db.commit()
    await db.refresh(folder)
    return folder


@router.get("/{workspace_id}/folders", response_model=list[FolderOut])
async def list_folders(
    workspace_id: str, ctx: CurrentWorkspace, db: DB
) -> list[Folder]:
    rows = (
        await db.execute(select(Folder).where(Folder.workspace_id == ctx[0].id))
    ).scalars()
    return list(rows.all())


@router.put(
    "/{workspace_id}/folders/{folder_id}/acl",
    response_model=FolderOut,
    dependencies=[Depends(require_role(Role.WORKSPACE_ADMIN.value))],
)
async def set_folder_acl(
    workspace_id: str,
    folder_id: str,
    acl: dict[str, list[str]],
    ctx: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
) -> Folder:
    folder = (
        await db.execute(
            select(Folder).where(Folder.id == folder_id, Folder.workspace_id == ctx[0].id)
        )
    ).scalar_one_or_none()
    if not folder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")
    folder.acl = acl
    db.add(
        AuditLog(
            workspace_id=ctx[0].id,
            user_id=user.id,
            action="folder.set_acl",
            target_type="folder",
            target_id=folder.id,
            payload={"acl": acl},
        )
    )
    await db.commit()
    await db.refresh(folder)
    return folder


# ---------- Admin-only: list all users (needed for member picker) ----------


@router.get(
    "/_admin/users",
    response_model=list[dict],
    dependencies=[Depends(require_global_admin)],
)
async def list_all_users(db: DB) -> list[dict]:
    users = (await db.execute(select(User))).scalars().all()
    return [
        {"id": u.id, "email": u.email, "display_name": u.display_name, "is_active": u.is_active}
        for u in users
    ]
