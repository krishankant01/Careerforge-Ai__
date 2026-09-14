"""
File upload validation (spec section 29).

We never trust the client-supplied filename or Content-Type header for
anything except a first-pass rejection — the actual proof a file "is" a
PDF/DOCX is its magic-byte signature, checked here, and later the fact that
our extraction library can actually parse it (extraction.py raises
CorruptFileError if not). This layered check is what "MIME type" validation
means in practice for these two formats.
"""
import os

from app.core.errors import FileTooLargeError, UnsupportedFileTypeError

# DOCX (and all modern Office formats) are ZIP archives: PK\x03\x04 signature.
_DOCX_SIGNATURE = b"PK\x03\x04"
_PDF_SIGNATURE = b"%PDF-"

_EXTENSION_TO_TYPE = {".pdf": "pdf", ".docx": "docx"}


def validate_extension(filename: str, allowed_extensions: list[str]) -> str:
    """Returns the normalized file_type ("pdf"/"docx"). Raises
    UnsupportedFileTypeError otherwise. Extension is checked case-insensitively
    and the path is never used for anything but this check — the actual
    storage filename is always server-generated (see resume_service)."""
    _, ext = os.path.splitext(filename.lower())
    if ext not in allowed_extensions:
        raise UnsupportedFileTypeError(allowed_extensions)
    return _EXTENSION_TO_TYPE[ext]


def validate_size(size_bytes: int, max_mb: int) -> None:
    max_bytes = max_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileTooLargeError(max_mb)


def validate_signature(content: bytes, file_type: str) -> bool:
    """Checks the file's actual bytes match what its extension claims.
    Returns False (never raises) so the caller can decide the exact error —
    used as the first line of defense; extraction.py is the authoritative
    check since it actually has to parse the file."""
    if file_type == "pdf":
        return content.startswith(_PDF_SIGNATURE)
    if file_type == "docx":
        return content.startswith(_DOCX_SIGNATURE)
    return False
