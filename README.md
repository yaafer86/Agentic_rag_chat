# Agentic RAG Chat Platform

> A secure, modular agentic RAG platform: free chat, workspace/subfolder-scoped RAG, isolated code interpreter, Neo4j knowledge graph, anti-hallucination VLM ingestion, Excel KPI engine, and custom dashboard builder.

This README is the **executable technical specification** for AI-assisted development (Claude Code, Qwen Code, Cursor, etc.).

---

## Key Features

- **Free Chat** — General conversation plus ad-hoc file uploads (temporary processing).
- **Scoped RAG** — Query documents organized by workspace / subfolder with granular access control.
- **Code Interpreter** — Isolated Python execution (Microsandbox) with inline chart rendering and `.docx`, `.xlsx`, `.pdf`, `.pptx` generation.
- **Knowledge Graph** — Neo4j indexed by theme, timeline, locality, and entity relationships.
- **Dashboards & KPI** — Excel/statistics engine, KPI extraction/validation, dynamic view builder with cross-filters.
- **Anti-Hallucination VLM Pipeline** — Structured extraction of tables/charts from images/PDF/Office with Pydantic validation, OCR fallback, and confidence scoring.
- **Multi-LLM Routing** — Ollama, LMStudio, OpenRouter, Anthropic, OpenAI via LiteLLM (dynamic selection, no hardcoded models).
- **RBAC Administration** — Global Admin (system) + Workspace Admin (members, ACL, quotas, models) + full audit trail.
- **Accessible UX** — Dark/light themes, right-to-left (RTL) chat preview for Arabic/Hebrew/Persian, live "thinking" stream showing the model's reasoning in real time.

---

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌────────────────────┐
│   Frontend      │◄────►│   API Gateway    │◄────►│  Backend (FastAPI) │
│ (Vite + React)  │      │ (CORS, JWT, Rate)│      │ + LangGraph Agent  │
└─────────────────┘      └──────────────────┘      └─────────┬──────────┘
                                                             │
        ┌──────────────┬──────────────┬──────────┬───────────┼──────────┐
        ▼              ▼              ▼          ▼           ▼          ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
   │PostgreSQL│  │ Qdrant   │  │ Neo4j    │ │ MinIO  │ │ Micro- │ │ LiteLLM  │
   │ (Users,  │  │(Vectors) │  │ (Graph)  │ │(Files) │ │sandbox │ │ (Router) │
   │  RBAC,   │  │          │  │          │ │        │ │(Docker)│ │          │
   │ Metadata)│  └──────────┘  └──────────┘ └────────┘ └────────┘ └────┬─────┘
   └──────────┘                                                        │
                                                        ┌──────────────┼──────────────┐
                                                        ▼              ▼              ▼
                                                     Ollama        OpenRouter     OpenAI/Anthropic
```

---

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Frontend** | Vite + React 18 + Zustand + React Query + shadcn/ui + Recharts/Plotly + React Flow | SPA, state, dataviz, KG viz |
| **Backend** | Python 3.11 + FastAPI + LangGraph + Pydantic v2 | REST/WS API, agent orchestration, validation |
| **Auth & RBAC** | JWT (httpOnly) + PostgreSQL RLS + Casbin | Workspace/subfolder isolation |
| **Vector DB** | Qdrant | Hybrid dense+sparse search, native metadata filtering |
| **Graph DB** | Neo4j | Entities/relations, theme/timeline/locality indexes, Cypher |
| **Metadata DB** | PostgreSQL 15+ | Users, workspaces, ACL, custom KPIs, audit logs |
| **Storage** | MinIO (S3-compatible) | Raw files, sandbox artifacts, exports |
| **Code Sandbox** | Microsandbox (ephemeral Docker + cgroups + seccomp) | Isolated Python execution, 30s timeout, no network |
| **LLM Router** | LiteLLM | Routing, fallback, cost tracking, semantic caching |
| **VLM Pipeline** | Generic VLM + Doctr OCR + Pydantic validation | Structured extraction, confidence scoring, fallback |

---

## Project Structure

```
agentic-rag-platform/
├── frontend/                 # Vite + React
│   ├── src/
│   │   ├── components/       # UI atoms/molecules (AdaptiveResults, DashboardBuilder, KGViewer, ThinkingStream, ThemeToggle...)
│   │   ├── features/         # Chat, Workspace, Sandbox, Admin, Auth, Settings
│   │   ├── hooks/            # useQuery, useAuth, useSandbox, useIntentRouter, useDirection, useTheme
│   │   ├── lib/              # API client, utils, formatters, i18n (dir detection)
│   │   └── store/            # Zustand stores (auth, theme, chat)
│   └── package.json
├── backend/                  # FastAPI + LangGraph
│   ├── app/
│   │   ├── agents/           # LangGraph workflows (chat, code, kg, dashboard)
│   │   ├── api/              # Routers (auth, chat, upload, sandbox, kg, dashboard, admin)
│   │   ├── core/             # Config, security, DB connections, LiteLLM router
│   │   ├── ingestion/        # Parsers, VLM pipeline, chunking, embedding
│   │   ├── models/           # Pydantic schemas
│   │   └── services/         # Qdrant, Neo4j, Sandbox, KPI engine
│   └── requirements.txt
├── infra/                    # Docker, docker-compose, DB/Neo4j/Qdrant init scripts
├── docs/                     # OpenAPI, JSON schemas, diagrams
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ / Node 20+
- 16GB RAM minimum (Neo4j + local LLMs)

### 1. Configuration
```bash
cp .env.example .env
# Edit .env with your provider keys, paths, JWT secret, etc.
```

### 2. Infrastructure
```bash
cd infra
docker compose up -d postgres qdrant neo4j minio ollama
```

### 3. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Environment Variables (`.env.example`)

See `.env.example` for the complete, commented template. Summary:

- **Auth & App** — `JWT_SECRET`, `APP_BASE_URL`, `API_BASE_URL`
- **Databases** — `POSTGRES_URL`, `QDRANT_URL`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- **Storage** — `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE`
- **LLM Routing** (endpoints/keys only — **no model names**) — `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_BASE_URL`, `LMSTUDIO_URL`, `LITELLM_DEFAULT_TIMEOUT`, `LITELLM_MAX_RETRIES`
- **Code Sandbox** — `SANDBOX_IMAGE`, `SANDBOX_TIMEOUT`, `SANDBOX_MAX_MEMORY_MB`, `SANDBOX_NETWORK_ENABLED`
- **Extraction & Validation** — `VLM_TEMPERATURE`, `OCR_FALLBACK_THRESHOLD`, `MAX_CONTEXT_TOKENS`, `ENABLE_SEMANTIC_CACHE`

---

## Dynamic Model Configuration

Model selection is resolved **at runtime** via `workspace.model_prefs` (PostgreSQL JSONB) plus an optional API payload override. No model is hardcoded anywhere.

```json
// workspace.model_prefs (example)
{
  "rag_model": "anthropic/claude-3-5-sonnet-20241022",
  "vlm_model": "qwen/qwen2.5-vl-72b-instruct",
  "agent_model": "openai/gpt-4o-mini",
  "fallback_chain": ["openrouter/meta-llama/llama-3.3-70b", "ollama/mistral:7b"],
  "max_tokens": 4096,
  "temperature": 0.3,
  "enable_cache": true,
  "cost_budget_usd": 5.00
}
```

**Backend resolution order:** `api_override` → `workspace_prefs` → `default_fallback`. Uses LiteLLM's native `fallbacks=[]`.

---

## Core Modules & Workflows

### 1. Anti-Hallucination VLM Ingestion
`Image → classification → structured JSON prompt (Pydantic) → VLM execution (T=0.2) → logical validation → if confidence < threshold → Doctr/OCR fallback → scoring → storage + "⚠️ Needs review" badge if < 0.7`

### 2. Scoped RAG & Intent Routing
- Qdrant hybrid search (dense + sparse) with **mandatory** metadata filter (`workspace_id`, `folder_path`, `user_acl`).
- Intent detection: `summarize`, `list`, `timeline`, `map`, `export`.
- If `> 100 results` → aggregate in Neo4j/SQL first. Never inject raw result sets into the LLM.
- Hard limit: 1000 DB rows. Soft default: 50.

### 3. Microsandbox & File Generation
- Endpoint: `POST /api/sandbox/run` → `{ code, files: [base64], timeout, memory_mb }`
- Output: `{ stdout, stderr, plots: [base64], artifacts: [{ name, mime, base64 }] }`
- Libraries: `pandas`, `numpy`, `matplotlib`, `plotly`, `python-docx`, `openpyxl`, `reportlab`, `python-pptx`.

### 4. Knowledge Graph (Neo4j)
- NER/RE extraction → async `MERGE` → composite indexes `(workspace_id, theme/name/date)`.
- Parameterized Cypher queries for timelines, localities, entity networks.
- Interactive visualization via React Flow.

### 5. KPI Engine & Dashboard Builder
- Excel parsing (`openpyxl` / `pandas`) → table/KPI detection → 3-layer validation (type, arithmetic, cross-source).
- Custom KPIs: formula + filters + unit + thresholds → stored as executable metadata.
- Source-driven builder: drag-and-drop widgets, synchronized global filters, export via sandbox (PDF/PPTX/PNG).
- Transparency: tooltip with source + formula + last-updated + confidence score.

### 6. UX: Thinking Stream, Themes, RTL
- **Thinking Stream** — When the model is reasoning (extended thinking, agent planning, or tool selection), a collapsible panel streams the intermediate reasoning tokens to the user in real time (SSE/WebSocket). Users can follow along, pause, or hide it. The content is auditable and logged.
- **Dark / Light Theme** — Tailwind `class` strategy toggled from a Zustand store, persisted to `localStorage`, defaults to `prefers-color-scheme`. Every component authored in both palettes; shadcn tokens drive the palette.
- **Right-to-Left (RTL) Preview** — The chat preview and message bubbles auto-detect direction per message. If language is RTL (Arabic, Hebrew, Persian, Urdu), the preview flips using CSS logical properties (`margin-inline-start`, `padding-inline-end`, `dir="rtl"` on the bubble). User preference can pin the direction globally. Detection uses Unicode script ranges on the first strong character.

---

## Administration & RBAC

| Role | Scope | Permissions |
|------|-------|-------------|
| `global_admin` | Entire system | CRUD users/workspaces, configure providers, audit logs, global metrics, controlled impersonation |
| `workspace_admin` | Assigned workspace | Invite/remove members, manage roles, subfolder ACL, `model_prefs`, quotas, shared dashboards |
| `workspace_editor` | Assigned workspace | Upload, RAG chat, sandbox, KPIs/dashboards, export |
| `workspace_viewer` | Assigned workspace | Read-only: RAG chat, dashboard viewing, PDF export |

**Admin endpoints:**
- `/api/admin/users` & `/api/admin/workspaces` (`global_admin`)
- `/api/workspaces/{id}/members` & `/api/workspaces/{id}/folders/acl` (`workspace_admin`)
- `/api/admin/audit` (`global_admin`)
- `/api/admin/providers` (`global_admin`)

**Rules:**
- Strict isolation: `workspace_admin` never sees another workspace.
- `global_admin` impersonation: read-only by default; write requires a temporary 15-minute token and is always logged.
- Quotas: block upload at 100%, alert at 80%.
- Every admin action → `audit_logs`.

---

## Security & Governance

- **Row-Level Security (RLS)** active on PostgreSQL — automatic injection of `workspace_id` + `user_acl`.
- **Mandatory metadata filtering** in Qdrant/Neo4j — never client-side.
- **Hardened Microsandbox** — `--cap-drop=ALL`, `no-new-privileges`, `network=none`, read-only FS except `/tmp`.
- **Strict validation** — Pydantic v2 `strict=True` for all LLM/VLM inputs and outputs.
- **Complete audit** — structured logs, KPI traceability, graph access history.

---

## AI-Assisted Development Guide (Claude / Qwen / Cursor)

### Strict Rules
1. **Never disable metadata filtering** in Qdrant/Neo4j. Always inject `workspace_id` + `user_acl` at the service layer.
2. **Context window** — aggregate first (SQL/Neo4j), then inject only the summary + top-K chunks.
3. **VLM** — Pydantic v2 `strict=True`. On failure: OCR fallback → score → UI flag.
4. **Sandbox** — no network access ever. Strict timeout. Clean `/tmp`. Collect artifacts only.
5. **Models** — resolve via `workspace.model_prefs` + payload. Never hardcode.
6. **RBAC** — RLS plus FastAPI middleware (`@require_role`, `@check_folder_acl`) before any business logic.

### Implementation Order
1. `infra/docker-compose.yml` + `.env` + init DB/Neo4j/Qdrant/MinIO
2. `backend/core/` (config, LiteLLM, DB clients, RLS middleware)
3. `backend/api/auth/` + `backend/models/` (Pydantic schemas)
4. `backend/ingestion/` (parsers, VLM pipeline, chunking, embedding)
5. `backend/services/qdrant.py` & `neo4j.py` (hybrid search, Cypher templates)
6. `backend/api/chat.py` & `agents/` (LangGraph workflows, intent routing, thinking-stream SSE)
7. `backend/services/sandbox.py` & `api/sandbox.py` (Microsandbox, file generation)
8. `backend/api/admin/` + RBAC policies + audit logs
9. `frontend/` (Vite setup, auth, chat UI with thinking stream + RTL + theme, admin dashboard, KG viewer, dashboard builder)
10. E2E tests, load testing, monitoring (LangSmith/Sentry/Prometheus)

### Validation Checklist
- [ ] RLS active on all sensitive tables + cross-workspace leak tests
- [ ] Metadata filter applied systematically in Qdrant/Neo4j
- [ ] VLM output Pydantic-validated + retry ×2 max + OCR fallback
- [ ] Sandbox isolated + timeout + no network + cleanup
- [ ] Intent routing detects `> 100 results` → automatic aggregation
- [ ] Custom KPIs stored + recomputable + source/formula tooltip
- [ ] Dashboard export via sandbox, not frontend
- [ ] Structured audit logs for every admin action
- [ ] Dynamic model resolution (workspace prefs + fallback chain)
- [ ] Quota check before upload + UI alerts
- [ ] Thinking stream endpoint returns SSE; UI renders collapsible panel
- [ ] Chat preview flips to RTL for Arabic/Hebrew/Persian/Urdu messages
- [ ] Every component renders correctly in both dark and light themes

---

## Handling 500+ Results — Adaptive Query Strategy

### Principle
> **No brute-force display, ever.** The system must always (1) understand intent, (2) adapt the response (aggregate / paginate / visualize), (3) give the user control to explore.

### Four-Layer Processing

**Layer 1 — Intent Detection (Agent Router)**
```python
INTENT_CLASSES = {
    "list_all":   "show all items (rare, requires pagination)",
    "summarize":  "summarize trends, stats, patterns",
    "compare":    "compare subsets (by theme, date, place)",
    "drill_down": "zoom into a specific subset",
    "export":     "generate a file (xlsx/pdf) with all results",
}
```
The agent auto-detects or asks: *"Would you like a summary, a paginated list, or a visualization?"*

**Layer 2 — Hybrid Queries (Vector + Neo4j + SQL)**

| Query type | Source | Strategy |
|-----------|--------|----------|
| Semantic search | Qdrant | `top_k=50` + re-ranking + metadata filter |
| Structured aggregation | Neo4j | `MATCH (e:Event) WHERE ... RETURN e.theme, count(*), avg(e.confidence)` |
| Exhaustive listing | PostgreSQL | Server-side pagination (`LIMIT 50 OFFSET 0`) + cursor |
| Visualization | Combo | Aggregates → chart, raw data → download |

Smart aggregation Cypher:
```cypher
MATCH (e:Event)-[:OCCURRED_IN]->(l:Location {name: $location})
WHERE e.date STARTS WITH $year
WITH e.theme AS theme, count(*) AS cnt,
     collect({title: e.title, date: e.date})[..10] AS samples
RETURN theme, cnt, samples
ORDER BY cnt DESC
LIMIT 20
```

**Layer 3 — Adaptive UX (Frontend)**

| Intent | UI rendering | User controls |
|--------|--------------|---------------|
| `summarize` | Summary cards + chart (Recharts) + LLM insights | Filter by theme/date, export summary |
| `list_all` | Paginated table (50/row) + inline search + sort | Pagination, CSV/XLSX export, column picker |
| `timeline` | Interactive chronology (vis-timeline) | Zoom, temporal filters, PNG/PDF export |
| `map` | Interactive map (Leaflet/MapLibre) with clusters | Geographic filters, detail popovers |
| `export` | Progress bar + notification on completion | Choose format (xlsx/pdf), pick fields |

**Layer 4 — Post-Processing Agent (LangGraph)**
When > 100 results are detected, the agent automatically proposes:
```
🔍 327 events found. What would you like to do?
[✓] Automatic summary by theme and period
[ ] Full paginated list (50/page)
[ ] Visualization: timeline / map / graph
[ ] Export everything as Excel/PDF
[ ] Refine: add a filter (date, type, place...)
```

### Unified Backend Endpoint
```python
@app.post("/api/query")
async def smart_query(
    query: str,
    workspace_id: str,
    max_results: int = Field(default=50, ge=1, le=1000),
    intent: Literal["auto", "summarize", "list", "timeline", "map"] = "auto",
    aggregation: Optional[Dict] = None,
    export_format: Optional[Literal["json", "xlsx", "pdf"]] = None,
    user: User = Depends(get_current_user),
):
    # 1. Auth + scope resolution
    # 2. Intent detection (LLM or rule-based)
    # 3. Hybrid query execution
    # 4. Post-processing (aggregate / paginate / summarize)
    # 5. Return structured response + UI hints
```

### Limits & Best Practices

| Constraint | Solution |
|-----------|----------|
| LLM context window | Never inject 500 raw chunks — always aggregate first |
| UI performance | Virtual scrolling for lists > 100 items, lazy-load charts |
| LLM cost | Two-pass summaries: (1) raw stats via SQL/Neo4j, (2) LLM insight over aggregates |
| Data freshness | Semantic cache per query + invalidation on upload |
| Accessibility | Text alternatives for charts, keyboard navigation on tables |

---

## Roadmap

| Phase | Scope | Deliverables |
|-------|-------|--------------|
| **P0** | Infra & Auth | Docker, JWT, PostgreSQL RLS, LiteLLM, MinIO, Vite shell |
| **P1** | Upload & VLM | Parser, VLM + Pydantic + OCR pipeline, chunking, Qdrant |
| **P2** | Scoped RAG & Chat | Hybrid search, metadata filtering, ACL, chat UI, thinking stream, RTL, theme toggle |
| **P3** | Microsandbox & File Generation | Docker executor, inline charts, docx/xlsx/pdf/pptx |
| **P4** | Neo4j KG | Entity/relation extraction, async MERGE, indexes, Cypher, viz |
| **P5** | Admin, KPI & Dashboards | RBAC, custom KPI builder, dynamic charts, export |
| **P6** | Production Ready | Monitoring, fallback routing, cost tracking, CI/CD |

---

> **For Claude Code / Qwen Code:** Use this README as the master specification. Implement phase by phase. Validate each module against the security and validation constraints before moving on. Favor robustness, data isolation, and traceability over prompt complexity.

**Ready for development.**
