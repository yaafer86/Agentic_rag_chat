"""RAG orchestration: intent → hybrid search or aggregation → synthesize.

Emits events through an async generator so the chat endpoint can forward them
as SSE frames. Events:

- thinking:      internal reasoning step, human-readable, optional
- tool_call:     name + args of a retrieval/aggregation op about to run
- tool_result:   compact result snapshot (count, sources)
- chunk:         model output chunk (for streaming synthesis)
- done:          final payload with content + sources + meta
- error:         terminal error
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from app.agents import intent as intent_mod
from app.core.litellm_router import ResolvedModel, astream, resolve_model
from app.ingestion.embedding import embed_texts
from app.services import neo4j as kg_svc
from app.services import qdrant as qsvc

logger = logging.getLogger(__name__)

AGGREGATE_THRESHOLD = 100
DEFAULT_TOP_K = 50


def _event(kind: str, **data: Any) -> dict[str, Any]:
    return {"event": kind, **data}


async def run_rag(
    *,
    workspace_id: str,
    query: str,
    model_prefs: dict[str, Any],
    max_results: int = DEFAULT_TOP_K,
    intent_override: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Main RAG loop. Yields events; terminal event is `done` or `error`."""
    try:
        classified = intent_mod.classify(query)
        intent = intent_override or classified.intent
        yield _event(
            "thinking",
            content=f"Intent detected: {intent} (confidence {classified.confidence:.2f}).",
        )

        try:
            rag_model: ResolvedModel | None = resolve_model(model_prefs, "rag_model")
        except ValueError as e:
            yield _event(
                "thinking",
                content=f"No rag_model configured ({e}); proceeding in deterministic mode.",
            )
            rag_model = None

        try:
            embed_model: ResolvedModel | None = resolve_model(model_prefs, "embedding_model")
        except ValueError:
            embed_model = None

        # Embed the query once for any vector search path.
        qvec = None
        if embed_model is not None:
            yield _event("tool_call", name="embed_query", args={"len": len(query)})
            try:
                [qvec] = await embed_texts(embed_model, [query])
            except Exception as e:
                yield _event(
                    "thinking",
                    content=f"Embedding unavailable ({e}); skipping vector search.",
                )
                qvec = None
        else:
            yield _event(
                "thinking",
                content="No embedding_model configured; skipping vector search.",
            )

        hits: list[dict[str, Any]] = []
        aggregated: dict[str, Any] | None = None

        if qvec is not None and intent in {
            "summarize", "list_all", "drill_down", "compare", "chat"
        }:
            yield _event("tool_call", name="qdrant.hybrid_search", args={"top_k": max_results})
            try:
                hits = await qsvc.hybrid_search(
                    query_vector=qvec,
                    workspace_id=workspace_id,
                    top_k=max_results,
                )
            except Exception as e:
                yield _event("thinking", content=f"Vector store unavailable ({e}).")
                hits = []
            yield _event("tool_result", name="qdrant.hybrid_search", count=len(hits))

        if intent == "timeline":
            yield _event("tool_call", name="neo4j.timeline")
            try:
                events = await kg_svc.timeline(workspace_id=workspace_id, limit=max_results)
            except Exception as e:
                yield _event("thinking", content=f"KG unavailable ({e}).")
                events = []
            aggregated = {"kind": "timeline", "events": events}
            yield _event("tool_result", name="neo4j.timeline", count=len(events))

        elif intent in {"summarize", "list_all"} and len(hits) >= AGGREGATE_THRESHOLD:
            yield _event(
                "thinking",
                content=(
                    f"{len(hits)} results exceed the {AGGREGATE_THRESHOLD}-threshold — "
                    "aggregating by theme instead of injecting raw context."
                ),
            )
            try:
                by_theme = await kg_svc.aggregate_events_by_theme(
                    workspace_id=workspace_id, limit=20
                )
            except Exception:
                by_theme = []
            aggregated = {"kind": "theme_aggregation", "themes": by_theme}

        # Build final prompt for the RAG model. When aggregated, we inject the compact
        # summary; otherwise the top-K chunks. Raw dumps never go into the LLM at any size.
        context_text = _compose_context(hits, aggregated, max_chars=12_000)
        sources = _extract_sources(hits)

        system_prompt = (
            "You are a careful analyst. Answer using ONLY the provided context. "
            "Cite sources inline as [S1], [S2]. If the context is empty or the answer "
            "is not present, say so plainly instead of guessing."
        )
        user_prompt = (
            f"Question: {query}\n\n"
            f"Intent: {intent}\n\n"
            f"Context:\n{context_text or '[no context retrieved]'}"
        )

        accumulated: list[str] = []
        if rag_model is not None:
            yield _event("tool_call", name="llm.stream", args={"model": rag_model.model})
            try:
                async for chunk in astream(
                    rag_model,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                ):
                    delta = _chunk_text(chunk)
                    if delta:
                        accumulated.append(delta)
                        yield _event("chunk", content=delta)
            except Exception as e:
                fallback = _fallback_answer(query, hits, aggregated)
                accumulated.append(fallback)
                yield _event("chunk", content=fallback)
                yield _event(
                    "thinking",
                    content=f"LLM stream unavailable ({e}); returned deterministic summary.",
                )
        else:
            fallback = _fallback_answer(query, hits, aggregated)
            accumulated.append(fallback)
            yield _event("chunk", content=fallback)

        yield _event(
            "done",
            content="".join(accumulated).strip(),
            sources=sources,
            meta={
                "intent": intent,
                "intent_confidence": classified.confidence,
                "hit_count": len(hits),
                "aggregated": bool(aggregated),
            },
        )
    except Exception as e:
        logger.exception("rag loop failed")
        yield _event("error", message=str(e))


def _chunk_text(chunk: Any) -> str:
    """Extract text from a LiteLLM streaming chunk, tolerating shape variance."""
    try:
        return chunk["choices"][0]["delta"]["content"] or ""
    except Exception:
        try:
            return chunk.choices[0].delta.content or ""
        except Exception:
            return ""


def _compose_context(
    hits: list[dict[str, Any]],
    aggregated: dict[str, Any] | None,
    *,
    max_chars: int,
) -> str:
    if aggregated:
        if aggregated["kind"] == "timeline":
            rows = [
                f"{e.get('date', '?')}: {e.get('title', '')} — {e.get('theme', '')}"
                for e in aggregated["events"]
            ]
            return "Timeline:\n" + "\n".join(rows[:200])
        if aggregated["kind"] == "theme_aggregation":
            rows = [
                f"- {t.get('theme', '?')}: {t.get('cnt', 0)} items"
                for t in aggregated.get("themes", [])
            ]
            return "Counts by theme:\n" + "\n".join(rows)
    if not hits:
        return ""
    pieces: list[str] = []
    total = 0
    for i, h in enumerate(hits, start=1):
        snippet = (h.get("text") or "").strip().replace("\n", " ")
        label = f"[S{i}]"
        line = f"{label} {snippet}"
        if total + len(line) > max_chars:
            break
        pieces.append(line)
        total += len(line)
    return "\n".join(pieces)


def _extract_sources(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, h in enumerate(hits, start=1):
        out.append(
            {
                "label": f"S{i}",
                "document_id": h.get("document_id"),
                "folder_id": h.get("folder_id"),
                "score": h.get("score"),
                "page_number": h.get("page_number"),
            }
        )
    return out


def _fallback_answer(
    query: str, hits: list[dict[str, Any]], aggregated: dict[str, Any] | None
) -> str:
    if aggregated and aggregated["kind"] == "theme_aggregation":
        themes = aggregated.get("themes", [])
        return (
            f"Found {sum(t.get('cnt', 0) for t in themes)} matching items across "
            f"{len(themes)} themes. (LLM offline: deterministic summary only.)"
        )
    if aggregated and aggregated["kind"] == "timeline":
        return f"Found {len(aggregated['events'])} timeline entries. (LLM offline.)"
    if hits:
        return f"Found {len(hits)} passages matching '{query}'. (LLM offline: no synthesis.)"
    return (
        f"No context retrieved for '{query}'. Upload documents or refine the query. "
        "(LLM offline.)"
    )


__all__ = ["AGGREGATE_THRESHOLD", "DEFAULT_TOP_K", "run_rag"]
