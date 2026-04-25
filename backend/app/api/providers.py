"""Provider discovery + model-test endpoints.

These power the Settings UI: pick a model from a live-discovered list,
then verify it actually responds.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.rbac import CurrentUser, CurrentWorkspace
from app.services.providers import discover_all, test_model

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("/models")
async def list_models(_user: CurrentUser) -> dict[str, Any]:
    """Probe every configured provider in parallel and return their model lists."""
    results = await discover_all()
    return {
        "providers": [
            {
                "provider": r.provider,
                "ok": r.ok,
                "models": r.models,
                "error": r.error,
            }
            for r in results
        ],
        "all_models": sorted({m for r in results for m in r.models}),
    }


@router.post("/test-model")
async def test(
    body: dict[str, Any],
    _user: CurrentUser,
    _ctx: CurrentWorkspace,
) -> dict[str, Any]:
    """Send a minimal completion through LiteLLM to confirm the model responds."""
    model = body.get("model")
    prompt = body.get("prompt", "Say 'pong' and nothing else.")
    if not isinstance(model, str) or not model:
        return {"ok": False, "error": "model required"}
    return await test_model(model, prompt)
