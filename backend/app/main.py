from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    # TODO (P0): initialize DB pool, Qdrant client, Neo4j driver, LiteLLM router.
    yield
    # TODO (P0): close connections cleanly.


settings = get_settings()

app = FastAPI(
    title="Agentic RAG API",
    version="0.0.1",
    lifespan=lifespan,
)

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


# TODO (P0): include routers from app.api (auth, chat, upload, sandbox, kg, dashboard, admin).
