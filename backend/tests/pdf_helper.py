"""
Builds a minimal but structurally valid single-page PDF containing given
lines of text, with correctly computed xref byte offsets (not hardcoded) so
it's genuinely parseable — not just a file that starts with "%PDF-".
pypdf's PdfReader.extract_text() can read text back out of this.
"""


def build_minimal_pdf(lines: list[str]) -> bytes:
    content_lines = "\n".join(f"BT /F1 11 Tf 50 {750 - i * 16} Td ({_escape(line)}) Tj ET" for i, line in enumerate(lines))
    content_stream = content_lines.encode("latin-1")

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n"
        + content_stream
        + b"\nendstream"
    )

    header = b"%PDF-1.4\n"
    body = bytearray()
    offsets = [0]  # object 0 is the free-list head, not written
    pos = len(header)

    for i, obj in enumerate(objects, start=1):
        offsets.append(pos)
        obj_bytes = f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
        body += obj_bytes
        pos += len(obj_bytes)

    xref_offset = pos
    xref = [b"xref", f"0 {len(objects) + 1}".encode(), b"0000000000 65535 f "]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n ".encode())
    xref_block = b"\n".join(xref) + b"\n"

    trailer = (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF"
    )

    return header + bytes(body) + xref_block + trailer


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
