# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run dev server
uvicorn app.main:app --reload --port 8000

# Run all tests (SQLite, no infrastructure required)
pytest

# Run a single test file
pytest tests/test_chat.py

# Run a single test
pytest tests/test_chat.py::test_function_name -v

# Lint + type-check
ruff check .
ruff format --check .
mypy app
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # dev server on :3000
npm run build        # tsc typecheck + vite build
npm run typecheck    # tsc --noEmit only
npm run lint         # eslint src
```

### Infrastructure (Docker Compose)

```bash
cd infra
docker compose up -d postgres qdrant neo4j minio ollama
```

### Database migrations (production PostgreSQL only)

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "description"
```

Dev/test uses SQLite with `create_all` automatically; Alembic is only for production PostgreSQL.

---

## Architecture

### Service topology

```
Browser (Vite + React 18)
  └── FastAPI backend (:8000)
        ├── PostgreSQL — users, workspaces, RLS, chat history, KPIs, audit logs
        ├── Qdrant — dense vector store (collection: rag_chunks)
        ├── Neo4j — knowledge graph (entities, events, relations)
        ├── MinIO — raw files + sandbox artifacts (key prefix: <workspace_id>/<doc_id>/…)
        ├── Microsandbox — ephemeral Docker containers for code execution
        └── LiteLLM — multi-provider LLM router (Ollama, LMStudio, OpenRouter, OpenAI, Anthropic)
```

### Backend module map

| Module | Role |
|--------|------|
| `app/core/config.py` | Pydantic `Settings` loaded from `.env`; obtain via `get_settings()` (cached) |
| `app/core/db.py` | Async SQLAlchemy engine + `session_scope(user_id, workspace_id)` which sets RLS context vars |
| `app/core/security.py` | bcrypt password hashing (sha256 pre-hash), HS256 JWT issue/decode |
| `app/core/rbac.py` | FastAPI dependencies: `CurrentUser`, `CurrentWorkspace`, `GlobalAdmin`, `require_role()`, `check_folder_acl()` |
| `app/core/litellm_router.py` | `resolve_model()` + `acomplete()` / `astream()` / `aembed()` — always goes through LiteLLM |
| `app/models/db.py` | SQLAlchemy ORM: `User`, `Workspace`, `WorkspaceMember`, `Folder`, `Document`, `ChatMessage`, `CustomKPI`, `Dashboard`, `AuditLog`, `ApiKey` |
| `app/models/schemas.py` | Pydantic v2 request/response schemas |
| `app/ingestion/pipeline.py` | Top-level orchestrator: parse → VLM/OCR → chunk → embed → upsert |
| `app/ingestion/vlm.py` | `extract_page()` — VLM call at T=0.2, strict Pydantic validation, retries×2 then `None` |
| `app/ingestion/ocr.py` | Doctr OCR fallback for failed VLM extractions |
| `app/ingestion/chunking.py` | `chunk_text()` — ~500 token chunks, 50-token overlap |
| `app/ingestion/embedding.py` | `embed_texts()` — batched in 64, delegates to LiteLLM |
| `app/ingestion/kg_extract.py` | NER/RE extraction via VLM → Pydantic → Neo4j MERGE |
| `app/agents/intent.py` | Rule-based intent classifier: returns one of `summarize`, `list_all`, `timeline`, `map`, `export`, `compare`, `drill_down`, `chat` |
| `app/agents/rag.py` | `run_rag()` async generator — yields SSE events: `thinking`, `tool_call`, `tool_result`, `chunk`, `done`, `error` |
| `app/services/qdrant.py` | `hybrid_search()` with **mandatory** `workspace_id` filter; `upsert()`, `delete_document()` |
| `app/services/neo4j.py` | Parameterized Cypher: `timeline()`, `entity_network()`, `aggregate_events_by_theme()` |
| `app/services/minio.py` | MinIO S3-compatible object storage |
| `app/services/sandbox.py` | Docker executor: cap_drop=ALL, network=none, read-only FS |
| `app/services/kpi.py` | AST-whitelist formula evaluator + 3-layer KPI validation + Excel table detection |

### Frontend module map

| Path | Role |
|------|------|
| `src/lib/api.ts` | Axios client with Bearer token injection + silent refresh on 401; `openChatStream()` uses `fetch` (not `EventSource`) to send Authorization header |
| `src/store/auth.ts` | Zustand auth store: hydrates from `localStorage`, auto-refreshes |
| `src/store/workspace.ts` | Zustand workspace store |
| `src/store/theme.ts` | Zustand theme store — `dark` class on `<html>`, persisted to `localStorage` |
| `src/lib/direction.ts` | Per-message RTL detection via Unicode script range of first strong character |
| `src/features/` | One subfolder per tab: `chat`, `sandbox`, `kg`, `dashboard`, `settings`, `admin`, `auth` |
| `src/components/ThinkingStream.tsx` | Collapsible panel that renders `thinking`/`tool_call`/`tool_result` SSE events |
| `src/components/MessageBubble.tsx` | Chat bubble with per-message `dir` detection |

---

## Key Conventions

### Model resolution — never hardcode a model name

All LLM calls resolve via `resolve_model(workspace.model_prefs, kind, override)`. Resolution order: `api_override` → `workspace.model_prefs[kind]` → `default` argument. LiteLLM uses `workspace.model_prefs.fallback_chain` automatically. If no model is configured, `resolve_model` raises `ValueError`; `run_rag` catches this and degrades gracefully.

```python
from app.core.litellm_router import resolve_model, acomplete
model = resolve_model(workspace.model_prefs, "rag_model")  # or "vlm_model", "agent_model", "embedding_model"
resp = await acomplete(model, messages)
```

### Workspace isolation — mandatory at every data layer

- **PostgreSQL**: always use `session_scope(user_id=..., workspace_id=...)` so RLS context variables (`app.current_user`, `app.current_workspace`) are set before any query.
- **Qdrant**: `workspace_id` is a required filter in `hybrid_search()`. It is built into the function — callers cannot omit it.
- **Neo4j**: every Cypher helper in `services/neo4j.py` takes `workspace_id` as a required parameter. No string interpolation of user input — use `$params` only.
- **MinIO**: object keys are prefixed with `<workspace_id>/<document_id>/`.

### RBAC dependency chain

Endpoints use FastAPI `Depends` in this order:
1. `CurrentUser` — decodes JWT, loads user row, checks `is_active`
2. `CurrentWorkspace` — resolves `X-Workspace-Id` header or path/query param, verifies membership
3. `require_role("workspace_editor", "workspace_admin")` — enforces minimum role
4. `GlobalAdmin` — for admin-only endpoints (`require_global_admin`)
5. `check_folder_acl(folder.acl, user.id, member.role, action)` — folder-level ACL

### SSE streaming pattern

`GET /api/chat/stream` returns an `EventSourceResponse`. Each `run_rag` event is forwarded as:
```
event: <kind>
data: <json>
```
Frontend uses `fetch()` (not `EventSource`) to support the `Authorization` header. The frontend `openChatStream()` in `src/lib/api.ts` handles SSE frame parsing manually.

### VLM ingestion pattern

`extract_page()` → strict Pydantic `PageExtraction` → if returns `None` after 2 retries → `ocr_image()` fallback → confidence score stored on `Document`. Documents with `confidence < 0.7` are flagged in the UI.

### KPI formula safety

Formulas are evaluated through an AST whitelist (`services/kpi.py:evaluate_formula`). No `eval`, no attribute access. Only: arithmetic ops, comparisons, boolean ops, constants, named variables, and the functions `min`, `max`, `sum`, `abs`, `round`, `avg`, `sqrt`.

### Result aggregation rule

When `len(hits) >= 100` (the `AGGREGATE_THRESHOLD`), `run_rag` switches from injecting raw chunk text to `neo4j.aggregate_events_by_theme()`. Raw chunk dumps never go into the LLM context at any size.

### Test environment

Tests run against SQLite (`sqlite+aiosqlite:///{tmp}/test.db`) via `conftest.py` which sets `POSTGRES_URL` and `JWT_SECRET` env vars before imports. Each test that uses `client` fixture gets a fresh schema (drop + create all). Services like Qdrant, Neo4j, and MinIO are not started; tests that need them mock or skip.

### Linting configuration

Backend uses `ruff` (line length 110, Python 3.11 target). Ignored rules: `S101` (assert), `S105` (hardcoded-password false positives on token type strings), `S608` (Cypher templates use allowlists not user input), `B008` (FastAPI `Depends()` in defaults). Security rules (`S`) are fully disabled in `tests/`.

Frontend uses ESLint with TypeScript parser. Formatting via Prettier (config in `frontend/.prettierrc`).

### First user becomes global admin

`POST /api/auth/register` checks if any user exists; if not, the new user gets `is_global_admin=True`. This is the bootstrap mechanism — there is no separate admin creation command.

### Auth tokens

- Access token: HS256 JWT, 60-minute TTL, `type=access`
- Refresh token: HS256 JWT, 14-day TTL, `type=refresh`
- Both carry a `jti` nonce. Tokens are stored in `localStorage` (not httpOnly cookies) and injected as `Authorization: Bearer <token>` by the Axios interceptor.
- On 401 response, the Axios interceptor attempts a silent refresh once before failing.

### Sandbox execution

`POST /api/sandbox/run` runs Python in a Docker container with `--cap-drop=ALL --no-new-privileges --network=none --read-only --tmpfs /sandbox --tmpfs /tmp`. Timeout enforced by `container.wait(timeout=N)` + forced stop. Output collected from `/sandbox/out/` archive.
