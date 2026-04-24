from app.ingestion import parsers


def test_plain_text() -> None:
    units = parsers.parse("notes.txt", b"hello world", "text/plain")
    assert len(units) == 1
    assert units[0].kind == "text"
    assert units[0].text == "hello world"


def test_markdown_fallback() -> None:
    units = parsers.parse("readme.md", b"# Title\n\nBody.", "text/markdown")
    assert units[0].text.startswith("# Title")


def test_image_roundtrip() -> None:
    png_signature = b"\x89PNG\r\n\x1a\n"  # minimal valid header prefix
    units = parsers.parse("pic.png", png_signature, "image/png")
    assert units[0].kind == "image"
    assert units[0].image_bytes == png_signature
    assert units[0].image_mime == "image/png"


def test_guess_mime_from_extension() -> None:
    assert parsers.guess_mime("foo.txt", None) == "text/plain"
    assert parsers.guess_mime("foo.xlsx", "application/octet-stream").startswith("application/")
