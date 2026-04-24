"""Entity / relation extraction for Neo4j ingestion.

The LLM is asked to return a strict Pydantic-validated JSON structure. Relation
types are clamped to a fixed allowlist so we can safely template them into
Cypher without injection risk.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.litellm_router import ResolvedModel, acomplete
from app.services import neo4j as kg

logger = logging.getLogger(__name__)


# Keep this list small and semantically meaningful; extend as needs grow.
RELATION_ALLOWLIST: frozenset[str] = frozenset(
    {
        "RELATED_TO",
        "PART_OF",
        "LOCATED_IN",
        "OCCURRED_IN",
        "OWNED_BY",
        "WORKS_FOR",
        "MENTIONS",
    }
)

EntityKind = Literal["person", "organization", "location", "event", "product", "concept"]


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ExtractedEntity(Strict):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    kind: EntityKind
    aliases: list[str] = Field(default_factory=list)
    date: str | None = None
    theme: str | None = None
    description: str = ""


class ExtractedRelation(Strict):
    src: str
    dst: str
    type: str
    evidence: str = ""


class KGExtraction(Strict):
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]


_SYSTEM = """You extract entities and relations from a passage. Output ONLY a JSON
object with this exact shape:

{
  "entities": [
    {"id": "<slug>", "name": "...", "kind": "person|organization|location|event|product|concept",
     "aliases": [], "date": "YYYY-MM-DD or null", "theme": "<short>", "description": "..."}
  ],
  "relations": [
    {"src": "<entity id>", "dst": "<entity id>",
     "type": "RELATED_TO|PART_OF|LOCATED_IN|OCCURRED_IN|OWNED_BY|WORKS_FOR|MENTIONS",
     "evidence": "<short verbatim quote>"}
  ]
}

Rules:
- Only use relation types from the allowlist. If nothing matches, use RELATED_TO.
- IDs must be lowercase-slug (a-z0-9-).
- Do not invent entities or relations not supported by the text.
- Output JSON only, no markdown fencing.
"""


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(s: str) -> str:
    return _SLUG_RE.sub("-", s.lower()).strip("-") or "entity"


def parse_extraction(raw: str) -> KGExtraction:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    extraction = KGExtraction.model_validate(json.loads(cleaned))
    # Sanitize: clamp relation types and slugify ids.
    safe_entities = [
        e.model_copy(update={"id": _slugify(e.id) or _slugify(e.name)})
        for e in extraction.entities
    ]
    safe_relations: list[ExtractedRelation] = []
    for r in extraction.relations:
        t = r.type if r.type in RELATION_ALLOWLIST else "RELATED_TO"
        safe_relations.append(
            r.model_copy(
                update={
                    "src": _slugify(r.src),
                    "dst": _slugify(r.dst),
                    "type": t,
                }
            )
        )
    return KGExtraction(entities=safe_entities, relations=safe_relations)


async def extract_from_text(text: str, *, model: ResolvedModel) -> KGExtraction | None:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"Passage:\n{text[:6000]}"},
    ]
    try:
        resp = await acomplete(model, messages, temperature=0.1)
    except Exception as e:
        logger.warning("KG extraction call failed: %s", e)
        return None
    try:
        content = resp["choices"][0]["message"]["content"]
    except Exception:
        return None
    try:
        return parse_extraction(content)
    except (ValidationError, json.JSONDecodeError) as e:
        logger.warning("KG extraction parse failed: %s", e)
        return None


async def merge_into_graph(workspace_id: str, extraction: KGExtraction) -> None:
    """Persist entities + relations to Neo4j, filtering by relation allowlist."""
    for e in extraction.entities:
        props = {
            "aliases": e.aliases,
            "date": e.date,
            "theme": e.theme,
            "description": e.description,
        }
        # For events, we also want the label `Event` rather than `Entity`. Neo4j supports
        # multi-labelling via CALL; to keep the service simple, we still merge as Entity
        # and rely on `kind` to filter. Timeline queries already MATCH on kind when needed.
        await kg.upsert_entity(workspace_id, e.id, e.name, e.kind, props)
    for r in extraction.relations:
        if r.type not in RELATION_ALLOWLIST:
            continue
        await kg.upsert_relation(workspace_id, r.src, r.dst, r.type, {"evidence": r.evidence})


__all__ = [
    "RELATION_ALLOWLIST",
    "ExtractedEntity",
    "ExtractedRelation",
    "KGExtraction",
    "extract_from_text",
    "merge_into_graph",
    "parse_extraction",
]
