# Diagrams (SVG, light mode)

Standalone SVG renders of every Mermaid flowchart from `docs/ARCHITECTURE.md`, `docs/FLOWS.md`, and `docs/INSTALL.md`. Useful for slide decks, Word documents, printed runbooks, and any viewer that doesn't render Mermaid natively.

The `.mmd` source for each diagram sits next to its `.svg`. Edit the `.mmd`, then re-run `bash render.sh` to regenerate. Mermaid sources inside the markdown docs remain canonical — they re-render on GitHub for free.

| # | Diagram | Source markdown | SVG | Mermaid source |
|---|---------|-----------------|-----|----------------|
| 1 | Service topology | [ARCHITECTURE.md §1](../ARCHITECTURE.md#1-service-topology) | [service-topology.svg](./service-topology.svg) | [.mmd](./service-topology.mmd) |
| 2 | RBAC decision tree | [ARCHITECTURE.md §3](../ARCHITECTURE.md#3-auth--rbac-decision-tree) | [rbac-decision-tree.svg](./rbac-decision-tree.svg) | [.mmd](./rbac-decision-tree.mmd) |
| 3 | Read-path sequence | [ARCHITECTURE.md §4](../ARCHITECTURE.md#4-request-lifecycle-read-path) | [read-path-sequence.svg](./read-path-sequence.svg) | [.mmd](./read-path-sequence.mmd) |
| 4 | Write-path sequence | [ARCHITECTURE.md §5](../ARCHITECTURE.md#5-request-lifecycle-write-path--upload--ingestion) | [write-path-sequence.svg](./write-path-sequence.svg) | [.mmd](./write-path-sequence.mmd) |
| 5 | Model resolution | [ARCHITECTURE.md §7](../ARCHITECTURE.md#7-configuration-resolution-order) | [model-resolution.svg](./model-resolution.svg) | [.mmd](./model-resolution.mmd) |
| 6 | Theme + RTL | [ARCHITECTURE.md §8](../ARCHITECTURE.md#8-darklight--rtl-contract) | [theme-and-rtl.svg](./theme-and-rtl.svg) | [.mmd](./theme-and-rtl.mmd) |
| 7 | Auth & registration | [FLOWS.md §1](../FLOWS.md#1-authentication--registration) | [auth-and-registration.svg](./auth-and-registration.svg) | [.mmd](./auth-and-registration.mmd) |
| 8 | Ingestion pipeline | [FLOWS.md §2](../FLOWS.md#2-document-ingestion-vlm--ocr-fallback) | [ingestion-pipeline.svg](./ingestion-pipeline.svg) | [.mmd](./ingestion-pipeline.mmd) |
| 9 | RAG chat + thinking stream | [FLOWS.md §3](../FLOWS.md#3-rag-chat-with-thinking-stream) | [rag-chat-with-thinking.svg](./rag-chat-with-thinking.svg) | [.mmd](./rag-chat-with-thinking.mmd) |
| 10 | KG extraction & query | [FLOWS.md §4](../FLOWS.md#4-knowledge-graph-extraction--query) | [kg-extraction-and-query.svg](./kg-extraction-and-query.svg) | [.mmd](./kg-extraction-and-query.mmd) |
| 11 | Sandbox execution | [FLOWS.md §5](../FLOWS.md#5-microsandbox-execution) | [sandbox-execution.svg](./sandbox-execution.svg) | [.mmd](./sandbox-execution.mmd) |
| 12 | KPI definition & evaluation | [FLOWS.md §6](../FLOWS.md#6-kpi-definition--evaluation) | [kpi-definition-and-evaluation.svg](./kpi-definition-and-evaluation.svg) | [.mmd](./kpi-definition-and-evaluation.mmd) |
| 13 | Dashboard builder | [FLOWS.md §7](../FLOWS.md#7-dashboard-builder) | [dashboard-builder.svg](./dashboard-builder.svg) | [.mmd](./dashboard-builder.mmd) |
| 14 | Settings & live model wiring | [FLOWS.md §8](../FLOWS.md#8-settings-live-model-wiring) | [settings-live-models.svg](./settings-live-models.svg) | [.mmd](./settings-live-models.mmd) |
| 15 | RBAC enforcement (per-request) | [FLOWS.md §9](../FLOWS.md#9-rbac-enforcement-per-request) | [rbac-enforcement-sequence.svg](./rbac-enforcement-sequence.svg) | [.mmd](./rbac-enforcement-sequence.mmd) |
| 16 | End-to-end: a user asks a question | [FLOWS.md §10](../FLOWS.md#10-end-to-end-a-user-asks-a-question) | [end-to-end-question.svg](./end-to-end-question.svg) | [.mmd](./end-to-end-question.mmd) |
| 17 | First-run onboarding | [INSTALL.md §7](../INSTALL.md#7-first-run-setup) | [first-run-flow.svg](./first-run-flow.svg) | [.mmd](./first-run-flow.mmd) |

## Theming

All renders use Mermaid's built-in **light** theme with an explicit white background. The palette is tuned in [`.mermaid-config.json`](./.mermaid-config.json) — soft indigo accents, slate text, amber notes — so the SVGs stay readable in both light viewers and printed handouts.

## Regenerating

```bash
cd docs/diagrams
bash render.sh
```

The script downloads Chrome via Puppeteer the first time, so plan on ~1 minute on a fresh box. Subsequent runs render in ~2 seconds per diagram.

If you edit the Mermaid source in `ARCHITECTURE.md` / `FLOWS.md` / `INSTALL.md`, also update the matching `.mmd` file here (or re-run the extraction script in `docs/diagrams/extract.py`) and re-render.

## Converting to PNG / PDF / DOCX

```bash
# PNG (rsvg-convert, ImageMagick, or Inkscape)
rsvg-convert service-topology.svg -o service-topology.png

# PDF
rsvg-convert -f pdf service-topology.svg -o service-topology.pdf

# DOCX — paste the SVG into Word; modern Word renders SVG natively.
# Or convert via pandoc:
pandoc -o flows.docx \
  --from=markdown \
  ../FLOWS.md
```
