"""Neo4j driver + parameterized Cypher helpers with mandatory workspace filter."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import get_settings

CONSTRAINTS_AND_INDEXES = [
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE INDEX entity_ws_name IF NOT EXISTS FOR (e:Entity) ON (e.workspace_id, e.name)",
    "CREATE INDEX event_ws_date IF NOT EXISTS FOR (ev:Event) ON (ev.workspace_id, ev.date)",
    "CREATE INDEX event_ws_theme IF NOT EXISTS FOR (ev:Event) ON (ev.workspace_id, ev.theme)",
    "CREATE INDEX location_ws_name IF NOT EXISTS FOR (l:Location) ON (l.workspace_id, l.name)",
]


@lru_cache(maxsize=1)
def _driver():
    from neo4j import AsyncGraphDatabase

    s = get_settings()
    return AsyncGraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))


async def ensure_schema() -> None:
    d = _driver()
    async with d.session() as session:
        for stmt in CONSTRAINTS_AND_INDEXES:
            await session.run(stmt)


async def _run(cypher: str, **params: Any) -> list[dict[str, Any]]:
    d = _driver()
    async with d.session() as session:
        result = await session.run(cypher, **params)
        return [dict(record) async for record in result]


async def upsert_entity(
    workspace_id: str, entity_id: str, name: str, kind: str, props: dict[str, Any]
) -> None:
    await _run(
        """
        MERGE (e:Entity {id: $id})
        SET e.workspace_id = $ws, e.name = $name, e.kind = $kind, e += $props
        """,
        id=entity_id,
        ws=workspace_id,
        name=name,
        kind=kind,
        props=props,
    )


async def upsert_relation(
    workspace_id: str, src_id: str, dst_id: str, rel_type: str, props: dict[str, Any] | None = None
) -> None:
    # rel_type is constrained by extractor; validated caller-side against an allowlist.
    await _run(
        f"""
        MATCH (a:Entity {{id: $src, workspace_id: $ws}})
        MATCH (b:Entity {{id: $dst, workspace_id: $ws}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        """,
        src=src_id,
        dst=dst_id,
        ws=workspace_id,
        props=props or {},
    )


async def timeline(workspace_id: str, theme: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    cypher = """
        MATCH (ev:Event {workspace_id: $ws})
        WHERE $theme IS NULL OR ev.theme = $theme
        RETURN ev.id AS id, ev.title AS title, ev.date AS date,
               ev.theme AS theme, ev.description AS description
        ORDER BY ev.date ASC
        LIMIT $limit
    """
    return await _run(cypher, ws=workspace_id, theme=theme, limit=limit)


async def entity_network(workspace_id: str, entity_id: str, depth: int = 2) -> dict[str, Any]:
    cypher = """
        MATCH (e:Entity {id: $id, workspace_id: $ws})
        CALL {
            WITH e
            MATCH path = (e)-[*1..$depth]-(n:Entity {workspace_id: $ws})
            RETURN collect(DISTINCT n) AS neighbors, collect(DISTINCT relationships(path)) AS rels
        }
        RETURN e AS root, neighbors, rels
    """
    # Neo4j doesn't support parameterized depth in a fixed-length pattern; clamp it.
    depth = max(1, min(5, depth))
    cypher = cypher.replace("*1..$depth", f"*1..{depth}")
    rows = await _run(cypher, id=entity_id, ws=workspace_id)
    if not rows:
        return {"root": None, "nodes": [], "edges": []}
    return rows[0]


async def aggregate_events_by_theme(workspace_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return await _run(
        """
        MATCH (ev:Event {workspace_id: $ws})
        WITH ev.theme AS theme, count(*) AS cnt,
             collect({id: ev.id, title: ev.title, date: ev.date})[..10] AS samples
        RETURN theme, cnt, samples
        ORDER BY cnt DESC
        LIMIT $limit
        """,
        ws=workspace_id,
        limit=limit,
    )


async def healthcheck() -> bool:
    try:
        rows = await _run("RETURN 1 AS ok")
        return bool(rows) and rows[0].get("ok") == 1
    except Exception:
        return False


async def close() -> None:
    d = _driver()
    await d.close()


__all__ = [
    "aggregate_events_by_theme",
    "close",
    "ensure_schema",
    "entity_network",
    "healthcheck",
    "timeline",
    "upsert_entity",
    "upsert_relation",
]
