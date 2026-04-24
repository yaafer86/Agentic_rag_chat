"""Knowledge Graph API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.core.rbac import CurrentUser, CurrentWorkspace
from app.services import neo4j as kg

router = APIRouter(prefix="/api/kg", tags=["kg"])


def _wrap_kg(fn):
    async def wrapped(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"KG unavailable: {e}") from e
    return wrapped


@router.get("/timeline")
async def timeline(
    ctx: CurrentWorkspace,
    _user: CurrentUser,
    theme: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict]:
    ws, _ = ctx
    return await _wrap_kg(kg.timeline)(workspace_id=ws.id, theme=theme, limit=limit)


@router.get("/themes")
async def themes(
    ctx: CurrentWorkspace,
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    ws, _ = ctx
    return await _wrap_kg(kg.aggregate_events_by_theme)(workspace_id=ws.id, limit=limit)


@router.get("/entity/{entity_id}/network")
async def entity_network(
    entity_id: str,
    ctx: CurrentWorkspace,
    _user: CurrentUser,
    depth: int = Query(default=2, ge=1, le=5),
) -> dict:
    ws, _ = ctx
    return await _wrap_kg(kg.entity_network)(workspace_id=ws.id, entity_id=entity_id, depth=depth)
