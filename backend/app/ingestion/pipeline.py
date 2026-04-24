"""Ingestion orchestrator: parse → (optional VLM) → chunk → embed → upsert."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.litellm_router import ResolvedModel, resolve_model
from app.ingestion import parsers
from app.ingestion.chunking import Chunk, chunk_text
from app.ingestion.embedding import embed_texts
from app.ingestion.vlm import PageExtraction, extract_page
from app.models.db import Document
from app.services import qdrant as qsvc

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    document_id: str
    status: str
    chunk_count: int
    avg_confidence: float | None
    notes: str = ""


def _blocks_to_text(page: PageExtraction) -> str:
    out: list[str] = []
    for b in page.blocks:
        if b.kind == "text":
            out.append(b.content)
        elif b.kind == "table":
            header = " | ".join(b.headers)
            rows = "\n".join(" | ".join(row) for row in b.rows)
            out.append(f"{b.caption}\n{header}\n{rows}".strip())
        elif b.kind == "chart":
            out.append(f"[chart:{b.chart_type}] {b.title}: {b.series}")
    return "\n\n".join(p for p in out if p)


async def ingest_bytes(
    *,
    db: AsyncSession,
    workspace_id: str,
    folder_id: str | None,
    document_id: str,
    filename: str,
    mime: str,
    data: bytes,
    storage_key: str,
    model_prefs: dict[str, Any] | None,
) -> IngestResult:
    """Run the pipeline end-to-end. Assumes the `Document` row exists with status=pending."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise ValueError(f"document {document_id} not found")

    try:
        units = parsers.parse(filename, data, mime)
        vlm_model: ResolvedModel | None = None
        confidences: list[float] = []
        all_chunks: list[Chunk] = []
        for unit in units:
            if unit.kind == "image":
                if vlm_model is None:
                    vlm_model = resolve_model(model_prefs, "vlm_model")
                page = await extract_page(
                    unit.image_bytes or b"",
                    mime=unit.image_mime or "image/png",
                    page_number=unit.page_number,
                    model=vlm_model,
                )
                if page is None:
                    # OCR fallback. Imported lazily.
                    from app.ingestion.ocr import ocr_image

                    ocr = await ocr_image(unit.image_bytes or b"")
                    text = ocr.text
                    conf = ocr.confidence
                else:
                    text = _blocks_to_text(page)
                    conf = page.confidence
                confidences.append(conf)
                chunks = chunk_text(
                    text,
                    metadata={
                        "page_number": unit.page_number,
                        "source": "vlm" if page else "ocr",
                        "confidence": conf,
                    },
                )
                all_chunks.extend(chunks)
            else:
                chunks = chunk_text(
                    unit.text,
                    metadata={"page_number": unit.page_number, "source": "text"},
                )
                all_chunks.extend(chunks)

        if not all_chunks:
            doc.status = "empty"
            await db.commit()
            return IngestResult(document_id=document_id, status="empty", chunk_count=0, avg_confidence=None)

        embedding_model = resolve_model(model_prefs, "embedding_model")
        vectors = await embed_texts(embedding_model, [c.text for c in all_chunks])
        records = [
            qsvc.ChunkRecord(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                folder_id=folder_id,
                document_id=document_id,
                text=c.text,
                vector=v,
                metadata=c.metadata,
            )
            for c, v in zip(all_chunks, vectors, strict=True)
        ]
        await qsvc.upsert(records)

        avg = sum(confidences) / len(confidences) if confidences else None
        doc.status = "indexed"
        doc.confidence = avg
        doc.doc_metadata = {
            **(doc.doc_metadata or {}),
            "chunk_count": len(all_chunks),
            "pages": len(units),
        }
        await db.commit()
        return IngestResult(
            document_id=document_id, status="indexed", chunk_count=len(all_chunks), avg_confidence=avg
        )
    except Exception as e:
        logger.exception("ingestion failed")
        doc.status = "failed"
        doc.doc_metadata = {**(doc.doc_metadata or {}), "error": str(e)[:500]}
        await db.commit()
        raise


__all__ = ["IngestResult", "ingest_bytes"]
