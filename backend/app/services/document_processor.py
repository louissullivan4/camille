"""
Document processing utilities.

Phase 3: plain-text passthrough only.
Phase 5: replace extract_text_from_file with Unstructured.io integration.
"""


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: Source text to chunk.
        chunk_size: Maximum characters per chunk.
        overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        List of text chunks. Returns a single-element list if text fits in one chunk.
    """
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap

    return chunks


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from uploaded file bytes.

    Phase 3 implementation: returns UTF-8 decoded text for .txt files.
    All other formats are returned as best-effort UTF-8 decode.
    Phase 5 will replace this with Unstructured.io for PDF/DOCX/OCR.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename: Original filename (used for future format detection).

    Returns:
        Extracted text string.
    """
    return file_bytes.decode("utf-8", errors="replace")
