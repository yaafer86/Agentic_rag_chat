"""OCR fallback using Doctr. Imported lazily so the dependency is only loaded on use."""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    text: str
    confidence: float
    word_boxes: list[dict]


async def ocr_image(image_bytes: bytes) -> OcrResult:
    """Run Doctr on a single image. Returns the concatenated text and average confidence.

    Doctr is heavy; this is lazily imported so tests that don't exercise it don't pay
    the cost.
    """
    try:
        from doctr.io import DocumentFile
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Doctr is not installed. Add `python-doctr[torch]` to requirements to enable OCR."
        ) from e

    predictor = _get_predictor()
    doc = DocumentFile.from_images([image_bytes])  # type: ignore[arg-type]
    result = predictor(doc)
    text_parts: list[str] = []
    word_boxes: list[dict] = []
    confidences: list[float] = []
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                line_text = " ".join(w.value for w in line.words)
                text_parts.append(line_text)
                for w in line.words:
                    word_boxes.append(
                        {"text": w.value, "confidence": float(w.confidence), "box": list(w.geometry)}
                    )
                    confidences.append(float(w.confidence))
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return OcrResult(text="\n".join(text_parts), confidence=avg_conf, word_boxes=word_boxes)


_predictor = None


def _get_predictor():
    global _predictor
    if _predictor is None:  # pragma: no cover
        from doctr.models import ocr_predictor

        _predictor = ocr_predictor(pretrained=True)
    return _predictor


__all__ = ["OcrResult", "ocr_image"]
