# Documentation index

| File | Audience | Contents |
|------|----------|----------|
| [`INSTALL.md`](./INSTALL.md) | Operators / new contributors | Step-by-step from zero: prerequisites, infra (Docker compose), backend venv + Alembic + uvicorn, frontend npm + dev/build, first-run onboarding flow, production deployment notes, troubleshooting matrix |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Engineers / reviewers | Service topology, data ownership matrix, RBAC decision tree, request lifecycle (read + write paths), security envelope, model-resolution chain, dark-light + RTL contract |
| [`FLOWS.md`](./FLOWS.md) | Engineers / product | Per-feature Mermaid flowcharts: auth & registration, ingestion (VLM + OCR fallback), RAG chat with thinking stream, KG extraction & query, sandbox execution, KPI definition & evaluation, dashboard builder, settings & live model wiring, RBAC enforcement, end-to-end question flow |

All diagrams use Mermaid, which renders natively on GitHub — no external tooling required to read them. To render locally, paste a fenced ` ```mermaid ` block into https://mermaid.live or use a VS Code extension.

## Future deliverables (P6+)

| Path | Phase | Contents |
|------|-------|----------|
| `openapi.json` | P0+ | FastAPI auto-generated OpenAPI spec — fetch via `curl http://localhost:8000/openapi.json` |
| `schemas/` | P1 | JSON Schemas exported from Pydantic models (`PageExtraction`, `KGExtraction`, etc.) |
| `adr/` | Ongoing | Architecture Decision Records — one file per decision, dated |
| `runbook.md` | P6 | On-call playbook: rotation alerts, common incidents, recovery procedures |

Keep diagrams as source (Mermaid `.mmd` or Excalidraw `.excalidraw`) plus a rendered PNG when you add new ones, so changes stay reviewable in PRs.
