"""Embedding wrapper with batching."""
from __future__ import annotations

from app.core.litellm_router import ResolvedModel, aembed

BATCH = 64


async def embed_texts(model: ResolvedModel, texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i : i + BATCH]
        out.extend(await aembed(model, batch))
    return out


__all__ = ["embed_texts"]
