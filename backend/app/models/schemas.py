"""Pydantic schemas for API request/response."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Some workspace fields legitimately start with `model_` (model_prefs,
# model_override). Pydantic 2 reserves that prefix as a protected
# namespace by default and warns on every import; silence it globally
# for our schemas — none of these collide with BaseModel internals.
_RELAX = ConfigDict(protected_namespaces=())


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class _Relaxed(BaseModel):
    model_config = _RELAX


# ---------- Auth ----------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(ORM):
    id: str
    email: EmailStr
    display_name: str
    is_global_admin: bool
    is_active: bool
    created_at: datetime


# ---------- Workspace ----------


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = Field(default="", max_length=2048)


class WorkspaceOut(ORM):
    id: str
    name: str
    slug: str
    description: str
    model_prefs: dict[str, Any]
    quota_bytes: int
    used_bytes: int
    created_at: datetime


class ModelPrefs(_Relaxed):
    rag_model: str | None = None
    vlm_model: str | None = None
    agent_model: str | None = None
    embedding_model: str | None = None
    fallback_chain: list[str] = Field(default_factory=list)
    max_tokens: int = 4096
    temperature: float = 0.3
    enable_cache: bool = True
    cost_budget_usd: float | None = None


class MemberAdd(BaseModel):
    user_id: str
    role: Literal["workspace_admin", "workspace_editor", "workspace_viewer"]


class MemberOut(ORM):
    id: str
    user_id: str
    role: str
    created_at: datetime


class FolderCreate(BaseModel):
    path: str = Field(min_length=1, max_length=512)
    acl: dict[str, list[str]] = Field(default_factory=dict)


class FolderOut(ORM):
    id: str
    path: str
    acl: dict[str, Any]
    created_at: datetime


# ---------- Documents & Upload ----------


class DocumentOut(ORM):
    id: str
    workspace_id: str
    folder_id: str | None
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    confidence: float | None
    doc_metadata: dict[str, Any]
    created_at: datetime


# ---------- Chat ----------


class ChatRequest(_Relaxed):
    workspace_id: str
    conversation_id: str | None = None
    message: str
    model_override: str | None = None
    max_results: int = Field(default=50, ge=1, le=1000)
    intent: Literal["auto", "summarize", "list_all", "timeline", "map", "export"] = "auto"
    stream_thinking: bool = True


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    content: str
    thinking: str | None = None
    intent_detected: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------- Sandbox ----------


class SandboxRunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100_000)
    files: list[dict[str, str]] = Field(default_factory=list)
    timeout_s: int = Field(default=30, ge=1, le=300)
    memory_mb: int = Field(default=512, ge=128, le=2048)


class SandboxArtifact(BaseModel):
    name: str
    mime: str
    base64: str


class SandboxRunResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    plots: list[str] = Field(default_factory=list)
    artifacts: list[SandboxArtifact] = Field(default_factory=list)
    duration_ms: int


# ---------- Admin ----------


class AuditLogOut(ORM):
    id: str
    workspace_id: str | None
    user_id: str | None
    action: str
    target_type: str
    target_id: str | None
    payload: dict[str, Any]
    created_at: datetime


# ---------- KPI / Dashboard ----------


class CustomKPICreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    formula: str = Field(min_length=1, max_length=4096)
    unit: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    source_document_ids: list[str] = Field(default_factory=list)


class CustomKPIOut(ORM):
    id: str
    workspace_id: str
    name: str
    formula: str
    unit: str
    filters: dict[str, Any]
    thresholds: dict[str, Any]
    source_document_ids: list[str]
    created_at: datetime


class DashboardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    layout: dict[str, Any] = Field(default_factory=dict)
    global_filters: dict[str, Any] = Field(default_factory=dict)


class DashboardOut(ORM):
    id: str
    workspace_id: str
    name: str
    layout: dict[str, Any]
    global_filters: dict[str, Any]
    created_by: str
    created_at: datetime
