"""Text chunking with metadata preservation.

Uses a simple recursive splitter on paragraph / sentence / word boundaries, measuring
length in approximate tokens (4 chars per token heuristic). For production-grade token
accuracy, swap `_len` for a tiktoken call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_CHUNK_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 50


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


_SPLIT_LEVELS = ["\n\n", "\n", ". ", " "]


def _split(text: str, separator: str) -> list[str]:
    if not separator:
        return list(text)
    parts = text.split(separator)
    # Re-attach the separator except after the last piece, so content is not lost.
    return [p + separator for p in parts[:-1]] + [parts[-1]]


def chunk_text(
    text: str,
    *,
    target_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Split `text` into chunks of approximately `target_tokens` with token-level overlap."""
    meta = dict(metadata or {})
    text = text.strip()
    if not text:
        return []
    if approx_tokens(text) <= target_tokens:
        single = Chunk(text=text, metadata=dict(meta))
        single.metadata["chunk_index"] = 0
        single.metadata["chunk_count"] = 1
        return [single]

    pieces: list[str] = [text]
    for sep in _SPLIT_LEVELS:
        if all(approx_tokens(p) <= target_tokens for p in pieces):
            break
        new_pieces: list[str] = []
        for p in pieces:
            if approx_tokens(p) > target_tokens:
                new_pieces.extend(_split(p, sep))
            else:
                new_pieces.append(p)
        pieces = [p for p in new_pieces if p]

    # Merge greedily while respecting target size, with overlap tail re-used in the next.
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_tokens = 0
    for piece in pieces:
        ptoks = approx_tokens(piece)
        if buf_tokens + ptoks > target_tokens and buf:
            chunk_text_ = "".join(buf).strip()
            if chunk_text_:
                chunks.append(Chunk(text=chunk_text_, metadata=dict(meta)))
            # Keep last overlap_tokens worth of content as prefix.
            tail: list[str] = []
            tail_tokens = 0
            for t in reversed(buf):
                tail.insert(0, t)
                tail_tokens += approx_tokens(t)
                if tail_tokens >= overlap_tokens:
                    break
            buf = tail[:]
            buf_tokens = sum(approx_tokens(t) for t in buf)
        buf.append(piece)
        buf_tokens += ptoks
    if buf:
        final = "".join(buf).strip()
        if final:
            chunks.append(Chunk(text=final, metadata=dict(meta)))
    for i, c in enumerate(chunks):
        c.metadata["chunk_index"] = i
        c.metadata["chunk_count"] = len(chunks)
    return chunks


__all__ = ["DEFAULT_CHUNK_TOKENS", "DEFAULT_OVERLAP_TOKENS", "Chunk", "approx_tokens", "chunk_text"]
