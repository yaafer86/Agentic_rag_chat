from app.agents.intent import classify


def test_summarize_keywords() -> None:
    assert classify("Give me a summary of 2024 sales").intent == "summarize"
    assert classify("TL;DR please").intent == "summarize"
    assert classify("Résumé de la réunion").intent == "summarize"


def test_timeline() -> None:
    r = classify("Show a timeline of events in Paris")
    assert r.intent == "timeline"
    assert r.confidence >= 0.8


def test_map() -> None:
    assert classify("Where did these incidents occur?").intent == "map"
    assert classify("Show the map by region").intent == "map"


def test_export_with_format_hint() -> None:
    r = classify("Export all results to xlsx")
    assert r.intent == "export"
    assert r.hints.get("format") == "xlsx"


def test_export_maps_excel_to_xlsx() -> None:
    assert classify("download as Excel").hints.get("format") == "xlsx"


def test_compare() -> None:
    assert classify("Compare Q1 vs Q2 revenue").intent == "compare"


def test_list_all() -> None:
    assert classify("List all events").intent == "list_all"
    assert classify("Show every event").intent == "list_all"


def test_drill_down() -> None:
    assert classify("Drill down on Q3 only").intent == "drill_down"
    # "region" would match the map intent, so test a non-geographic drill.
    assert classify("Filter by priority high").intent == "drill_down"


def test_chat_fallback() -> None:
    assert classify("Who is the CEO?").intent == "chat"
    assert classify("").intent == "chat"
