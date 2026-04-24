from app.ingestion.chunking import chunk_text


def test_short_text_single_chunk() -> None:
    chunks = chunk_text("Hello world.", target_tokens=500)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world."
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].metadata["chunk_count"] == 1


def test_empty_yields_nothing() -> None:
    assert chunk_text("   \n\n  ") == []


def test_long_text_splits_and_overlaps() -> None:
    # ~8000 chars ≈ 2000 tokens → multiple chunks at target=200.
    paragraphs = []
    for i in range(40):
        paragraphs.append(
            f"Paragraph {i}. " + ("lorem ipsum dolor sit amet " * 10).strip() + "."
        )
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, target_tokens=200, overlap_tokens=40)
    assert len(chunks) > 3
    # Metadata is consistent.
    assert all(c.metadata["chunk_count"] == len(chunks) for c in chunks)
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))
    # Every paragraph body appears in at least one chunk (no content loss).
    for i in range(40):
        marker = f"Paragraph {i}."
        assert any(marker in c.text for c in chunks), marker


def test_metadata_passthrough() -> None:
    chunks = chunk_text("short", metadata={"source": "test", "page_number": 4})
    assert chunks[0].metadata["source"] == "test"
    assert chunks[0].metadata["page_number"] == 4
