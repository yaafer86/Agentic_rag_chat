"""FastAPI entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience: create tables if missing. Production uses Alembic migrations.
    from app.core.db import init_db

    await init_db()
    yield


settings = get_settings()

app = FastAPI(title="Agentic RAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


# Routers
from app.api import admin as _admin  # noqa: E402
from app.api import auth as _auth  # noqa: E402
from app.api import chat as _chat  # noqa: E402
from app.api import dashboard as _dashboard  # noqa: E402
from app.api import kg as _kg  # noqa: E402
from app.api import kpi as _kpi  # noqa: E402
from app.api import sandbox as _sandbox  # noqa: E402
from app.api import upload as _upload  # noqa: E402
from app.api import workspaces as _workspaces  # noqa: E402

app.include_router(_auth.router)
app.include_router(_workspaces.router)
app.include_router(_upload.router)
app.include_router(_chat.router)
app.include_router(_sandbox.router)
app.include_router(_kg.router)
app.include_router(_kpi.router)
app.include_router(_dashboard.router)
app.include_router(_admin.router)
