"""
Text extraction abstraction — Phase 5.

Centralises PDF/DOCX extraction so both resume_service and the RAG
pipeline share one extraction path rather than each implementing it.

Why a separate module?
- resume_service.py already extracts text for analysis scoring.
- The RAG pipeline needs to re-extract or reuse that text for chunking.
- Having one place makes it easy to add new file types (e.g. .txt, .md)
  without touching business-logic services.
"""
import io
from pathlib import Path


def extract_text(path: str | Path, file_type: str) -> str:
    """
    Extract plain text from a file.

    Args:
        path:      Absolute path to the file.
        file_type: Lowercase file type identifier: "pdf" | "docx" | "txt" | "md".

    Returns:
        Extracted text. Empty string if extraction fails.

    Raises:
        ValueError: If file_type is not supported.
    """
    file_type = file_type.lower().lstrip(".")
    path = Path(path)

    if file_type == "pdf":
        return _extract_pdf(path)
    if file_type in ("docx", "doc"):
        return _extract_docx(path)
    if file_type in ("txt", "md", "markdown"):
        return path.read_text(encoding="utf-8", errors="replace")

    raise ValueError(f"Unsupported file type: {file_type!r}")


def extract_text_from_bytes(data: bytes, file_type: str) -> str:
    """
    Extract text from in-memory bytes (e.g. uploaded file before saving).
    Same file_type rules as extract_text().
    """
    file_type = file_type.lower().lstrip(".")
    if file_type == "pdf":
        return _extract_pdf_bytes(data)
    if file_type in ("docx", "doc"):
        return _extract_docx_bytes(data)
    if file_type in ("txt", "md", "markdown"):
        return data.decode("utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {file_type!r}")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # lazy import — pypdf is optional dep
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except Exception:
        return ""


def _extract_pdf_bytes(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except Exception:
        return ""


def _extract_docx(path: Path) -> str:
    try:
        import docx  # python-docx
        doc = docx.Document(str(path))
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception:
        return ""


def _extract_docx_bytes(data: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(data))
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception:
        return ""
