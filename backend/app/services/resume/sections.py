"""
Section detection: splits raw resume text into (section_type, content)
chunks by matching common header lines. This is a heuristic, not an ML
classifier — resumes are semi-structured enough that "a short line that's
mostly one of these words" is a reliable signal, and it's fully
deterministic and instant, unlike sending the whole resume to an LLM just
to find out where "Experience" starts.

Anything before the first recognized header, or that doesn't match any
header at all, is filed under OTHER rather than dropped — Phase 3's "do not
hardcode scores" principle extends to "do not silently discard content"
too.
"""
import re

from app.models.resume import SectionType

_HEADER_PATTERNS: list[tuple[SectionType, re.Pattern]] = [
    (SectionType.SUMMARY, re.compile(r"^(summary|profile|objective|about me)\s*:?$", re.I)),
    (SectionType.SKILLS, re.compile(r"^(technical\s+)?skills?(\s+&\s+tools)?\s*:?$", re.I)),
    (SectionType.EDUCATION, re.compile(r"^education(al background)?\s*:?$", re.I)),
    (
        SectionType.EXPERIENCE,
        re.compile(r"^(work\s+)?experience|employment history\s*:?$", re.I),
    ),
    (SectionType.PROJECTS, re.compile(r"^(personal\s+|academic\s+)?projects?\s*:?$", re.I)),
    (
        SectionType.CERTIFICATIONS,
        re.compile(r"^(certifications?|licenses?)\s*:?$", re.I),
    ),
]

# A header line is short (resumes don't write paragraph-length headers) and
# doesn't end in a sentence-ending period, which would suggest prose instead.
_MAX_HEADER_LENGTH = 40


def _match_header(line: str) -> SectionType | None:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADER_LENGTH or stripped.endswith("."):
        return None
    for section_type, pattern in _HEADER_PATTERNS:
        if pattern.match(stripped):
            return section_type
    return None


def detect_sections(text: str) -> list[tuple[SectionType, int, str]]:
    """Returns a list of (section_type, order_index, content) tuples."""
    lines = text.splitlines()

    sections: list[tuple[SectionType, int, str]] = []
    current_type = SectionType.OTHER
    current_lines: list[str] = []
    order = 0

    def flush() -> None:
        nonlocal order
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_type, order, content))
            order += 1

    for line in lines:
        matched = _match_header(line)
        if matched is not None:
            flush()
            current_type = matched
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    return sections
