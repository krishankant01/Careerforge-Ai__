"""
Text chunking utilities — Phase 5 upgrade.

clean_text:  strips excess whitespace, normalises Unicode, removes HTML entities.
chunk_text:  word-boundary sliding window (generic — for resume raw_text, job JDs, etc.)
chunk_by_section: keeps a ResumeSection as a single chunk if it fits; otherwise splits.
              Sections have semantic unity (one topic per section) so splitting them
              loses less meaning than splitting mid-sentence across arbitrary boundaries.
"""
import html
import re
import unicodedata


def clean_text(text: str) -> str:
    """
    Normalize text before chunking or embedding.

    Steps:
    1. Decode HTML entities (&amp; → &, &nbsp; → space, etc.)
    2. Normalize Unicode to NFC (canonical composed form).
    3. Replace non-breaking spaces and zero-width chars with regular space.
    4. Collapse runs of whitespace other than newlines.
    5. Collapse runs of 3+ newlines to a single blank line.
    6. Strip leading/trailing whitespace.
    """
    text = html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    # Replace non-breaking space, zero-width space, etc. with regular space
    text = re.sub(r"[\u00a0\u200b\u200c\u200d\ufeff]", " ", text)
    # Collapse horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines → blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """
    Sliding-window chunker that breaks on word boundaries.

    Args:
        text:    Input text (will be cleaned first).
        size:    Target chunk length in characters.
        overlap: Number of characters of overlap between adjacent chunks.
                 Overlap prevents a key sentence being split exactly at a boundary.

    Returns:
        List of non-empty chunk strings.
    """
    text = clean_text(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        # Prefer to break at a word boundary
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(end - overlap, start + 1)
    return chunks


def chunk_by_section(content: str, max_size: int, overlap: int) -> list[str]:
    """
    Chunk strategy for ResumeSection rows.

    A resume section (Skills, Experience, ...) has inherent semantic unity.
    If the section fits in one chunk we keep it whole — splitting it never
    makes retrieval better.  Only if the section exceeds max_size do we
    fall back to the sliding window.
    """
    cleaned = clean_text(content)
    if not cleaned:
        return []
    if len(cleaned) <= max_size:
        return [cleaned]
    return chunk_text(cleaned, max_size, overlap)
