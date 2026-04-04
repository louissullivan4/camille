"""Tests for document_processor.py — chunk_text and extract_text_from_file."""

from app.services.document_processor import chunk_text, extract_text_from_file


class TestChunkText:
    def test_empty_string_returns_empty_list(self):
        assert chunk_text("") == []

    def test_short_doc_returns_single_chunk(self):
        text = "Short text."
        result = chunk_text(text, chunk_size=1000)
        assert result == ["Short text."]

    def test_exact_chunk_size_returns_single_chunk(self):
        text = "a" * 1000
        result = chunk_text(text, chunk_size=1000)
        assert len(result) == 1
        assert result[0] == text

    def test_chunk_text_respects_size(self):
        text = "a" * 2500
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        for chunk in chunks:
            assert len(chunk) <= 1000

    def test_chunk_text_overlap_content_preserved(self):
        # With chunk_size=10, overlap=3, text of 23 chars:
        # chunk 0: [0:10]
        # chunk 1: [7:17]
        # chunk 2: [14:24] (but text is 23 chars, so [14:23])
        text = "abcdefghijklmnopqrstuvw"  # 23 chars
        chunks = chunk_text(text, chunk_size=10, overlap=3)
        assert len(chunks) >= 2
        # Verify overlap: last 3 chars of chunk[0] == first 3 chars of chunk[1]
        assert chunks[0][-3:] == chunks[1][:3]

    def test_chunk_text_covers_all_content(self):
        text = "Hello World! This is a test of chunking with overlap."
        chunks = chunk_text(text, chunk_size=20, overlap=5)
        # Every character in the original text must appear in at least one chunk.
        # Simplest check: first chunk starts with beginning, last chunk ends with end.
        assert text[:20] == chunks[0]
        assert chunks[-1] in text  # last chunk is a substring of text
        assert text.endswith(chunks[-1])

    def test_multiple_chunks_produced_for_long_text(self):
        text = "x" * 3000
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        assert len(chunks) >= 3


class TestExtractTextFromFile:
    def test_utf8_text_file(self):
        content = "Hello, governance world!"
        result = extract_text_from_file(content.encode("utf-8"), "doc.txt")
        assert result == content

    def test_non_utf8_bytes_replaced_not_raised(self):
        bad_bytes = b"Good text \xff\xfe bad bytes"
        result = extract_text_from_file(bad_bytes, "doc.pdf")
        assert "Good text" in result
        # Should not raise; replacement chars present instead

    def test_empty_bytes_returns_empty_string(self):
        result = extract_text_from_file(b"", "empty.txt")
        assert result == ""
