"""Live provider discovery — queries each configured backend for its model list.

Every probe is time-boxed. Failures return an empty list with the error string
so the UI can render "unreachable" next to the provider name.
"""
from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = 5.0


@dataclass
class ProviderModels:
    provider: str
    ok: bool
    models: list[str]
    error: str | None = None


async def _ollama() -> ProviderModels:
    s = get_settings()
    url = s.ollama_base_url.rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(url)
            r.raise_for_status()
            names = [f"ollama/{m['name']}" for m in r.json().get("models", [])]
        return ProviderModels("ollama", True, names)
    except Exception as e:
        return ProviderModels("ollama", False, [], str(e)[:200])


async def _lmstudio() -> ProviderModels:
    s = get_settings()
    url = s.lmstudio_url.rstrip("/") + "/v1/models"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(url)
            r.raise_for_status()
            names = [f"lmstudio/{m['id']}" for m in r.json().get("data", [])]
        return ProviderModels("lmstudio", True, names)
    except Exception as e:
        return ProviderModels("lmstudio", False, [], str(e)[:200])


async def _openai() -> ProviderModels:
    s = get_settings()
    if not s.openai_api_key or s.openai_api_key.startswith("sk-..."):
        return ProviderModels("openai", False, [], "OPENAI_API_KEY not set")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {s.openai_api_key}"},
            )
            r.raise_for_status()
            names = [f"openai/{m['id']}" for m in r.json().get("data", [])]
        return ProviderModels("openai", True, names)
    except Exception as e:
        return ProviderModels("openai", False, [], str(e)[:200])


async def _openrouter() -> ProviderModels:
    s = get_settings()
    if not s.openrouter_api_key or s.openrouter_api_key.startswith("sk-or-..."):
        return ProviderModels("openrouter", False, [], "OPENROUTER_API_KEY not set")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {s.openrouter_api_key}"},
            )
            r.raise_for_status()
            names = [f"openrouter/{m['id']}" for m in r.json().get("data", [])]
        return ProviderModels("openrouter", True, names)
    except Exception as e:
        return ProviderModels("openrouter", False, [], str(e)[:200])


async def _anthropic() -> ProviderModels:
    """Anthropic doesn't expose a public /models listing; surface a curated static set
    when the key is configured so users can pick without free-typing."""
    s = get_settings()
    if not s.anthropic_api_key or s.anthropic_api_key.startswith("sk-ant-..."):
        return ProviderModels("anthropic", False, [], "ANTHROPIC_API_KEY not set")
    # Kept short on purpose — operators can always free-text a specific dated slug
    # in the model_prefs form.
    curated = [
        "anthropic/claude-opus-4-7",
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-haiku-4-5-20251001",
    ]
    return ProviderModels("anthropic", True, curated)


async def discover_all() -> list[ProviderModels]:
    """Query every configured provider in parallel."""
    import asyncio

    return list(
        await asyncio.gather(
            _ollama(),
            _lmstudio(),
            _openai(),
            _openrouter(),
            _anthropic(),
        )
    )


async def test_model(model: str, prompt: str = "ping") -> dict[str, Any]:
    """Send a minimal completion request to verify connectivity.

    Returns {"ok": bool, "latency_ms": int, "error": str | None, "sample": str}.
    """
    import time

    from app.core.litellm_router import ResolvedModel, acomplete

    start = time.monotonic()
    try:
        resolved = ResolvedModel(
            model=model,
            fallbacks=[],
            temperature=0.0,
            max_tokens=16,
            enable_cache=False,
        )
        resp = await acomplete(
            resolved, [{"role": "user", "content": prompt}], temperature=0.0, max_tokens=16
        )
        content = ""
        with contextlib.suppress(Exception):
            content = resp["choices"][0]["message"]["content"] or ""
        return {
            "ok": True,
            "latency_ms": int((time.monotonic() - start) * 1000),
            "error": None,
            "sample": content[:200],
        }
    except Exception as e:
        return {
            "ok": False,
            "latency_ms": int((time.monotonic() - start) * 1000),
            "error": str(e)[:500],
            "sample": "",
        }


__all__ = ["ProviderModels", "discover_all", "test_model"]
