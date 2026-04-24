"""Rule-based intent classifier with conservative defaults.

Output is one of: summarize, list_all, timeline, map, export, compare, drill_down, chat.
`chat` is the fallback for off-corpus / open-ended conversation.

This stays rule-based on purpose — it's zero-latency, auditable, and good enough for the
heuristic "over 100 results? aggregate first" routing. A caller can override with an
LLM-based classifier when requirements grow beyond keyword matching.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Intent = Literal[
    "summarize", "list_all", "timeline", "map", "export", "compare", "drill_down", "chat"
]


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    hints: dict[str, str]


_SUMMARIZE = re.compile(
    r"\b(summary|summarize|overview|tl;dr|recap|brief|synthesize|synth[èe]se|r[ée]sum[ée])\b",
    re.IGNORECASE,
)
_LIST_ALL = re.compile(
    r"\b(list(?:\s+all)?|show\s+all|all\s+(?:events?|documents?|items?|rows?)|every\s+\w+)\b",
    re.IGNORECASE,
)
_TIMELINE = re.compile(
    r"\b(timeline|chronolog(?:y|ical)|when|history|over\s+time|evolution|chronologie)\b",
    re.IGNORECASE,
)
_MAP = re.compile(
    r"\b(map|geographic(?:al)?|location|where|cartograph(?:y|ic)|region|cit(?:y|ies)|carte)\b",
    re.IGNORECASE,
)
_EXPORT = re.compile(
    r"\b(export|download|save\s+(?:as|to)\s+(?:xlsx|pdf|csv|excel)|generate\s+(?:a\s+)?(?:report|file))\b",
    re.IGNORECASE,
)
_COMPARE = re.compile(
    r"\b(compare|versus|vs\.?|diff(?:erence)?\s+between|side[- ]by[- ]side|compar(?:er|aison))\b",
    re.IGNORECASE,
)
_DRILL = re.compile(
    r"\b(drill\s*down|zoom\s+(?:in|on)|only\s+(?:for|in)|filter\s+by|narrow\s+(?:to|down))\b",
    re.IGNORECASE,
)


def classify(query: str) -> IntentResult:
    q = query.strip()
    if not q:
        return IntentResult("chat", 0.0, {})

    # Order matters: export / timeline / map have strong signal; summarize is the
    # gentlest fallback before chat.
    if _EXPORT.search(q):
        return IntentResult("export", 0.9, _export_hints(q))
    if _TIMELINE.search(q):
        return IntentResult("timeline", 0.85, {})
    if _MAP.search(q):
        return IntentResult("map", 0.85, {})
    if _COMPARE.search(q):
        return IntentResult("compare", 0.8, {})
    if _DRILL.search(q):
        return IntentResult("drill_down", 0.75, {})
    if _LIST_ALL.search(q):
        return IntentResult("list_all", 0.8, {})
    if _SUMMARIZE.search(q):
        return IntentResult("summarize", 0.8, {})
    # Questions that mention aggregate nouns without an explicit verb still want
    # summarization when we have many hits — caller upgrades later.
    return IntentResult("chat", 0.5, {})


def _export_hints(q: str) -> dict[str, str]:
    m = re.search(r"\b(xlsx|excel|pdf|csv|pptx|docx)\b", q, re.IGNORECASE)
    if m:
        fmt = m.group(1).lower()
        if fmt == "excel":
            fmt = "xlsx"
        return {"format": fmt}
    return {}


__all__ = ["Intent", "IntentResult", "classify"]
