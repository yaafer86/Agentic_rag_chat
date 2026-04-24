"""VLM-based structured extraction with Pydantic validation and OCR fallback.

The prompt asks the model to return a single JSON object matching the `PageExtraction`
schema. The output is strict-parsed; on failure the call retries once, then falls back
to OCR (see `app.ingestion.ocr`).
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import get_settings
from app.core.litellm_router import ResolvedModel, acomplete

logger = logging.getLogger(__name__)


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ExtractedText(Strict):
    kind: Literal["text"] = "text"
    content: str
    bbox: tuple[float, float, float, float] | None = None


class ExtractedTable(Strict):
    kind: Literal["table"] = "table"
    caption: str = ""
    headers: list[str]
    rows: list[list[str]]
    bbox: tuple[float, float, float, float] | None = None


class ExtractedChart(Strict):
    kind: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie", "scatter", "area", "other"]
    title: str = ""
    x_axis_label: str = ""
    y_axis_label: str = ""
    series: list[dict[str, Any]]
    bbox: tuple[float, float, float, float] | None = None


ExtractedBlock = ExtractedText | ExtractedTable | ExtractedChart


class PageExtraction(Strict):
    page_number: int = Field(ge=1)
    blocks: list[ExtractedText | ExtractedTable | ExtractedChart]
    language: str = "en"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    notes: str = ""


_PROMPT_SYSTEM = """You are a careful document extractor. Output ONLY valid JSON
that matches this schema:

{
  "page_number": <int>,
  "language": <ISO 639-1>,
  "confidence": <float 0..1>,
  "notes": <string, at most 240 chars>,
  "blocks": [
    {"kind": "text", "content": "<verbatim text>", "bbox": [x0,y0,x1,y1] or null},
    {"kind": "table", "caption": "...", "headers": [...], "rows": [[...], ...], "bbox": ...},
    {"kind": "chart", "chart_type": "bar|line|pie|scatter|area|other", "title": "...",
     "x_axis_label": "...", "y_axis_label": "...", "series": [{"name": "...", "data": [...]}],
     "bbox": ...}
  ]
}

Rules:
- Do NOT invent numbers or rows. If uncertain, leave notes and lower confidence.
- Preserve verbatim text. Do not summarize.
- Output JSON ONLY, no markdown fencing, no prose.
"""


def _image_message(image_bytes: bytes, mime: str) -> dict[str, Any]:
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract this page."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    }


def parse_page_extraction(raw: str) -> PageExtraction:
    """Parse JSON, stripping a single ```json fence if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    return PageExtraction.model_validate(json.loads(cleaned))


async def extract_page(
    image_bytes: bytes,
    *,
    mime: str,
    page_number: int,
    model: ResolvedModel,
    max_retries: int = 2,
) -> PageExtraction | None:
    """Run the VLM on a single page image.

    Returns None if all retries fail — caller should trigger OCR fallback.
    """
    s = get_settings()
    messages = [
        {"role": "system", "content": _PROMPT_SYSTEM},
        _image_message(image_bytes, mime),
    ]
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = await acomplete(model, messages, temperature=s.vlm_temperature)
            content = resp["choices"][0]["message"]["content"]
            page = parse_page_extraction(content)
            if page.page_number != page_number:
                page = page.model_copy(update={"page_number": page_number})
            return page
        except (ValidationError, json.JSONDecodeError, KeyError, RuntimeError) as e:
            last_err = e
            logger.warning("VLM extraction attempt %d failed: %s", attempt + 1, e)
    logger.error("VLM extraction giving up after %d attempts: %s", max_retries, last_err)
    return None


__all__ = [
    "ExtractedBlock",
    "ExtractedChart",
    "ExtractedTable",
    "ExtractedText",
    "PageExtraction",
    "extract_page",
    "parse_page_extraction",
]
