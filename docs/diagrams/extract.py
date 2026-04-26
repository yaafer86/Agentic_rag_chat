"""Extract every ```mermaid block from the docs into a .mmd file in this folder.

Run from the repo root:

    python3 docs/diagrams/extract.py

Block order in each markdown file must match the `names` list below — re-numbering
a block requires editing this script accordingly.
"""
from __future__ import annotations

import pathlib
import re
import sys

DOCS = [
    ("docs/ARCHITECTURE.md", [
        "service-topology",
        "rbac-decision-tree",
        "read-path-sequence",
        "write-path-sequence",
        "model-resolution",
        "theme-and-rtl",
    ]),
    ("docs/FLOWS.md", [
        "auth-and-registration",
        "ingestion-pipeline",
        "rag-chat-with-thinking",
        "kg-extraction-and-query",
        "sandbox-execution",
        "kpi-definition-and-evaluation",
        "dashboard-builder",
        "settings-live-models",
        "rbac-enforcement-sequence",
        "end-to-end-question",
    ]),
    ("docs/INSTALL.md", [
        "first-run-flow",
    ]),
]

PATTERN = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    out = repo_root / "docs" / "diagrams"
    out.mkdir(parents=True, exist_ok=True)

    total = 0
    for rel_path, names in DOCS:
        text = (repo_root / rel_path).read_text()
        blocks = PATTERN.findall(text)
        if len(blocks) != len(names):
            print(
                f"{rel_path}: found {len(blocks)} mermaid blocks, expected {len(names)}",
                file=sys.stderr,
            )
            return 1
        for name, block in zip(names, blocks, strict=True):
            target = out / f"{name}.mmd"
            target.write_text(block.rstrip() + "\n")
            print(f"wrote {target.relative_to(repo_root)}")
            total += 1
    print(f"\nTotal: {total} diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
