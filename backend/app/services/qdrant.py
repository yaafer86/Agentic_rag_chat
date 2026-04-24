"""Qdrant vector store wrapper with mandatory workspace/ACL filtering."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

COLLECTION = "rag_chunks"
VECTOR_SIZE_DEFAULT = 1536


@dataclass
class ChunkRecord:
    id: str
    workspace_id: str
    folder_id: str | None
    document_id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any]


@lru_cache(maxsize=1)
def _client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=get_settings().qdrant_url)


async def ensure_collection(vector_size: int = VECTOR_SIZE_DEFAULT) -> None:
    from qdrant_client.http import models as qm

    def _sync():
        c = _client()
        if COLLECTION not in {col.name for col in c.get_collections().collections}:
            c.create_collection(
                collection_name=COLLECTION,
                vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
            )
            for field in ("workspace_id", "folder_id", "document_id"):
                c.create_payload_index(
                    COLLECTION, field_name=field, field_schema=qm.PayloadSchemaType.KEYWORD
                )

    await asyncio.to_thread(_sync)


async def upsert(records: list[ChunkRecord]) -> None:
    from qdrant_client.http import models as qm

    def _sync():
        c = _client()
        c.upsert(
            collection_name=COLLECTION,
            points=[
                qm.PointStruct(
                    id=r.id,
                    vector=r.vector,
                    payload={
                        "workspace_id": r.workspace_id,
                        "folder_id": r.folder_id,
                        "document_id": r.document_id,
                        "text": r.text,
                        **r.metadata,
                    },
                )
                for r in records
            ],
        )

    await asyncio.to_thread(_sync)


async def hybrid_search(
    query_vector: list[float],
    *,
    workspace_id: str,
    folder_ids: list[str] | None = None,
    top_k: int = 50,
    text_must_contain: str | None = None,
) -> list[dict[str, Any]]:
    """Dense search with MANDATORY workspace filter. Keyword narrowing via payload match."""
    from qdrant_client.http import models as qm

    must: list[Any] = [qm.FieldCondition(key="workspace_id", match=qm.MatchValue(value=workspace_id))]
    if folder_ids:
        must.append(qm.FieldCondition(key="folder_id", match=qm.MatchAny(any=folder_ids)))
    if text_must_contain:
        must.append(qm.FieldCondition(key="text", match=qm.MatchText(text=text_must_contain)))

    def _sync() -> list[dict[str, Any]]:
        c = _client()
        hits = c.search(
            collection_name=COLLECTION,
            query_vector=query_vector,
            query_filter=qm.Filter(must=must),
            limit=top_k,
            with_payload=True,
        )
        return [{"id": h.id, "score": h.score, **(h.payload or {})} for h in hits]

    return await asyncio.to_thread(_sync)


async def delete_document(workspace_id: str, document_id: str) -> None:
    from qdrant_client.http import models as qm

    def _sync():
        c = _client()
        c.delete(
            collection_name=COLLECTION,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(key="workspace_id", match=qm.MatchValue(value=workspace_id)),
                        qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id)),
                    ]
                )
            ),
        )

    await asyncio.to_thread(_sync)


async def healthcheck() -> bool:
    try:
        def _sync():
            _client().get_collections()
        await asyncio.to_thread(_sync)
        return True
    except Exception:
        return False


__all__ = [
    "COLLECTION",
    "ChunkRecord",
    "delete_document",
    "ensure_collection",
    "healthcheck",
    "hybrid_search",
    "upsert",
]
