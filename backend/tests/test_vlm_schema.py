import json

import pytest
from pydantic import ValidationError

from app.ingestion.vlm import (
    ExtractedChart,
    ExtractedTable,
    ExtractedText,
    PageExtraction,
    parse_page_extraction,
)


def test_page_extraction_accepts_mixed_blocks() -> None:
    payload = {
        "page_number": 1,
        "language": "en",
        "confidence": 0.92,
        "notes": "",
        "blocks": [
            {"kind": "text", "content": "Hello"},
            {
                "kind": "table",
                "caption": "Revenue",
                "headers": ["Q", "USD"],
                "rows": [["Q1", "10"], ["Q2", "12"]],
            },
            {
                "kind": "chart",
                "chart_type": "bar",
                "title": "Revenue",
                "x_axis_label": "Q",
                "y_axis_label": "USD",
                "series": [{"name": "2024", "data": [10, 12]}],
            },
        ],
    }
    page = PageExtraction.model_validate(payload)
    assert page.page_number == 1
    assert isinstance(page.blocks[0], ExtractedText)
    assert isinstance(page.blocks[1], ExtractedTable)
    assert isinstance(page.blocks[2], ExtractedChart)


def test_strict_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PageExtraction.model_validate(
            {
                "page_number": 1,
                "language": "en",
                "confidence": 0.5,
                "notes": "",
                "blocks": [
                    {"kind": "text", "content": "x", "extra_junk": True},
                ],
            }
        )


def test_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        PageExtraction.model_validate(
            {
                "page_number": 1,
                "language": "en",
                "confidence": 1.5,
                "notes": "",
                "blocks": [],
            }
        )


def test_parse_handles_json_fence() -> None:
    fenced = "```json\n" + json.dumps(
        {
            "page_number": 2,
            "language": "fr",
            "confidence": 0.7,
            "notes": "",
            "blocks": [{"kind": "text", "content": "bonjour"}],
        }
    ) + "\n```"
    page = parse_page_extraction(fenced)
    assert page.page_number == 2
    assert page.language == "fr"
