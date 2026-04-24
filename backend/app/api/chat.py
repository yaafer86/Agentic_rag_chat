"""Chat endpoints: non-stream POST /api/chat, streaming SSE GET /api/chat/stream.

The SSE stream forwards each RAG event (`thinking`, `tool_call`, `tool_result`,
`chunk`, `done`, `error`) so the frontend can render the live thinking panel.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents.rag import run_rag
from app.core.rbac import DB, CurrentUser
from app.models.db import ChatMessage, Workspace, WorkspaceMember
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _resolve_workspace(
    db: AsyncSession, workspace_id: str, user: CurrentUser
) -> Workspace:
    ws = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace not found")
    if not user.is_global_admin:
        member = (
            await db.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == ws.id,
                    WorkspaceMember.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this workspace")
    return ws


async def _persist(
    db: AsyncSession,
    *,
    workspace_id: str,
    conversation_id: str,
    user_id: str,
    user_content: str,
    assistant_content: str,
    thinking: str,
    meta: dict,
) -> tuple[str, str]:
    user_msg = ChatMessage(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        user_id=user_id,
        role="user",
        content=user_content,
    )
    assistant_msg = ChatMessage(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        user_id=user_id,
        role="assistant",
        content=assistant_content,
        thinking=thinking or None,
        msg_metadata=meta,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()
    return user_msg.id, assistant_msg.id


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, user: CurrentUser, db: DB) -> ChatResponse:
    ws = await _resolve_workspace(db, body.workspace_id, user)
    conversation_id = body.conversation_id or str(uuid.uuid4())

    thinking_buf: list[str] = []
    content_buf: list[str] = []
    sources: list[dict] = []
    meta: dict = {}

    async for ev in run_rag(
        workspace_id=ws.id,
        query=body.message,
        model_prefs=dict(ws.model_prefs or {}),
        max_results=body.max_results,
        intent_override=None if body.intent == "auto" else body.intent,
    ):
        kind = ev.get("event")
        if kind == "thinking":
            thinking_buf.append(str(ev.get("content", "")))
        elif kind == "chunk":
            content_buf.append(str(ev.get("content", "")))
        elif kind == "done":
            if ev.get("content"):
                content_buf = [ev["content"]]
            sources = ev.get("sources", [])
            meta = ev.get("meta", {})
        elif kind == "error":
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, ev.get("message", "rag error"))

    content = "".join(content_buf).strip()
    thinking = "\n".join(thinking_buf).strip()

    _, assistant_id = await _persist(
        db,
        workspace_id=ws.id,
        conversation_id=conversation_id,
        user_id=user.id,
        user_content=body.message,
        assistant_content=content,
        thinking=thinking,
        meta=meta,
    )

    return ChatResponse(
        conversation_id=conversation_id,
        message_id=assistant_id,
        content=content,
        thinking=thinking if body.stream_thinking else None,
        intent_detected=meta.get("intent", "chat"),
        sources=sources,
        meta=meta,
    )


@router.get("/stream")
async def chat_stream(
    user: CurrentUser,
    db: DB,
    workspace_id: str = Query(..., description="target workspace"),
    q: str = Query(..., min_length=1, max_length=8000),
    conversation_id: str | None = Query(default=None),
    intent: str = Query(default="auto"),
    max_results: int = Query(default=50, ge=1, le=1000),
) -> EventSourceResponse:
    ws = await _resolve_workspace(db, workspace_id, user)
    conv_id = conversation_id or str(uuid.uuid4())

    async def _generator() -> AsyncIterator[dict]:
        thinking_buf: list[str] = []
        content_buf: list[str] = []
        async for ev in run_rag(
            workspace_id=ws.id,
            query=q,
            model_prefs=dict(ws.model_prefs or {}),
            max_results=max_results,
            intent_override=None if intent == "auto" else intent,
        ):
            kind = ev.get("event", "message")
            if kind == "thinking":
                thinking_buf.append(str(ev.get("content", "")))
            elif kind == "chunk":
                content_buf.append(str(ev.get("content", "")))
            yield {"event": kind, "data": json.dumps(ev)}

        try:
            await _persist(
                db,
                workspace_id=ws.id,
                conversation_id=conv_id,
                user_id=user.id,
                user_content=q,
                assistant_content="".join(content_buf).strip(),
                thinking="\n".join(thinking_buf).strip(),
                meta={},
            )
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"persist failed: {e}"})}

    return EventSourceResponse(_generator())


@router.get("/history")
async def chat_history(
    user: CurrentUser,
    db: DB,
    workspace_id: str = Query(...),
    conversation_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    ws = await _resolve_workspace(db, workspace_id, user)
    rows = (
        await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.workspace_id == ws.id,
                ChatMessage.conversation_id == conversation_id,
            )
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
    ).scalars()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "thinking": m.thinking,
            "metadata": m.msg_metadata,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]
