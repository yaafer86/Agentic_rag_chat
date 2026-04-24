"""Authentication and RBAC dependencies for FastAPI."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.security import decode_token
from app.models.db import Role, User, Workspace, WorkspaceMember


async def _db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


DB = Annotated[AsyncSession, Depends(_db)]


def _bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "malformed Authorization header")
    return parts[1]


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(_db),
) -> User:
    token = _bearer(authorization)
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not an access token")
    user_id = payload.get("sub")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_workspace(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(_db),
) -> tuple[Workspace, WorkspaceMember | None]:
    """Resolve the workspace from `X-Workspace-Id` header or path/query `workspace_id`."""
    workspace_id = (
        request.headers.get("X-Workspace-Id")
        or request.path_params.get("workspace_id")
        or request.query_params.get("workspace_id")
    )
    if not workspace_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "workspace_id required")
    ws = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace not found")
    membership = (
        await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws.id, WorkspaceMember.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not membership and not user.is_global_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this workspace")
    return ws, membership


CurrentWorkspace = Annotated[tuple[Workspace, WorkspaceMember | None], Depends(get_workspace)]


def require_role(*allowed: str):
    """Dependency factory enforcing a set of workspace roles (or global_admin)."""
    allowed_set = set(allowed)

    async def _check(
        ctx: CurrentWorkspace,
        user: CurrentUser,
    ) -> tuple[Workspace, WorkspaceMember | None]:
        _ws, member = ctx
        if user.is_global_admin:
            return ctx
        if not member or member.role not in allowed_set:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role in {sorted(allowed_set)}")
        return ctx

    return _check


def require_global_admin(user: CurrentUser) -> User:
    if not user.is_global_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "global admin required")
    return user


GlobalAdmin = Annotated[User, Depends(require_global_admin)]


def check_folder_acl(
    folder_acl: dict[str, Iterable[str]],
    user_id: str,
    member_role: str | None,
    required: str = "read",
) -> bool:
    """Evaluate a folder ACL entry.

    `folder_acl` example: {"read": ["user:uid", "role:workspace_editor"], "write": [...]}.
    An empty ACL for an action defers to workspace role. Explicit entries take precedence.
    """
    entries = list(folder_acl.get(required, []))
    if not entries:
        if required == "read":
            return True
        return member_role in {Role.WORKSPACE_ADMIN.value, Role.WORKSPACE_EDITOR.value}
    if f"user:{user_id}" in entries:
        return True
    return bool(member_role) and f"role:{member_role}" in entries


__all__ = [
    "DB",
    "CurrentUser",
    "CurrentWorkspace",
    "GlobalAdmin",
    "check_folder_acl",
    "get_current_user",
    "get_workspace",
    "require_global_admin",
    "require_role",
]
