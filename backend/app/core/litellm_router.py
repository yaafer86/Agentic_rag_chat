"""LiteLLM routing wrapper.

Resolves the target model via `workspace.model_prefs` + per-call overrides, and calls
LiteLLM with a fallback chain. LiteLLM is imported lazily so tests without the package
installed still work against the stub path.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import get_settings

_settings = get_settings()


@dataclass
class ResolvedModel:
    model: str
    fallbacks: list[str]
    temperature: float
    max_tokens: int
    enable_cache: bool


def resolve_model(
    prefs: dict[str, Any] | None,
    kind: Literal["rag_model", "vlm_model", "agent_model", "embedding_model"],
    override: str | None = None,
    default: str | None = None,
) -> ResolvedModel:
    prefs = prefs or {}
    model = override or prefs.get(kind) or default
    if not model:
        raise ValueError(
            f"no {kind} configured: set workspace.model_prefs.{kind} or pass an override"
        )
    return ResolvedModel(
        model=model,
        fallbacks=list(prefs.get("fallback_chain", [])),
        temperature=float(prefs.get("temperature", 0.3)),
        max_tokens=int(prefs.get("max_tokens", 4096)),
        enable_cache=bool(prefs.get("enable_cache", True)),
    )


async def acomplete(
    resolved: ResolvedModel,
    messages: list[dict[str, str]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Async chat completion via LiteLLM. Raises if LiteLLM is unavailable."""
    try:
        import litellm
    except ImportError as e:  # pragma: no cover - exercised only when litellm missing
        raise RuntimeError("litellm not installed") from e

    return await litellm.acompletion(
        model=resolved.model,
        messages=messages,
        temperature=kwargs.pop("temperature", resolved.temperature),
        max_tokens=kwargs.pop("max_tokens", resolved.max_tokens),
        fallbacks=resolved.fallbacks or None,
        timeout=_settings.litellm_default_timeout,
        num_retries=_settings.litellm_max_retries,
        **kwargs,
    )


async def astream(
    resolved: ResolvedModel,
    messages: list[dict[str, str]],
    **kwargs: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Async streaming. Yields LiteLLM-shaped chunks."""
    try:
        import litellm
    except ImportError as e:
        raise RuntimeError("litellm not installed") from e

    stream = await litellm.acompletion(
        model=resolved.model,
        messages=messages,
        temperature=kwargs.pop("temperature", resolved.temperature),
        max_tokens=kwargs.pop("max_tokens", resolved.max_tokens),
        fallbacks=resolved.fallbacks or None,
        stream=True,
        timeout=_settings.litellm_default_timeout,
        **kwargs,
    )
    async for chunk in stream:  # type: ignore[union-attr]
        yield chunk


async def aembed(
    resolved: ResolvedModel, inputs: list[str], **kwargs: Any
) -> list[list[float]]:
    try:
        import litellm
    except ImportError as e:
        raise RuntimeError("litellm not installed") from e
    resp = await litellm.aembedding(
        model=resolved.model,
        input=inputs,
        timeout=_settings.litellm_default_timeout,
        **kwargs,
    )
    return [d["embedding"] for d in resp["data"]]


__all__ = ["ResolvedModel", "acomplete", "aembed", "astream", "resolve_model"]
