"""
Deterministic job description parsing — the fallback (and first pass) used
whether or not an AI provider is configured. Mirrors
app/services/resume/sections.py's approach: header-line matching, not ML.

Job postings use a much more varied vocabulary for "here are the skills we
want" than resumes do for section headers, so this recognizes a broader set
of header phrasings than the resume parser does.
"""
import re

from app.services.resume.skills_taxonomy import lookup_skill, all_skill_names

_REQUIRED_HEADER_RE = re.compile(
    r"^(requirements?|required\s+skills?|qualifications?|what you.?ll need|minimum qualifications?)\s*:?$",
    re.I,
)
_PREFERRED_HEADER_RE = re.compile(
    r"^(preferred\s+(skills?|qualifications?)|nice\s+to\s+have|bonus\s+points?|good\s+to\s+have)\s*:?$",
    re.I,
)
_RESPONSIBILITY_HEADER_RE = re.compile(
    r"^(responsibilities|what you.?ll do|the role|duties|key responsibilities)\s*:?$", re.I
)
_MAX_HEADER_LENGTH = 60

_EXPERIENCE_YEARS_RE = re.compile(r"(\d+)\+?\s*(?:to\s*\d+\s*)?years?", re.I)
_DEGREE_RE = re.compile(
    r"(bachelor'?s|master'?s|b\.?s\.?|m\.?s\.?|phd|ph\.?d\.?)\s*(degree)?", re.I
)


def _classify_header(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADER_LENGTH or stripped.endswith("."):
        return None
    if _REQUIRED_HEADER_RE.match(stripped):
        return "required"
    if _PREFERRED_HEADER_RE.match(stripped):
        return "preferred"
    if _RESPONSIBILITY_HEADER_RE.match(stripped):
        return "responsibilities"
    return None


def split_job_sections(text: str) -> dict[str, list[str]]:
    """Returns {"required": [...], "preferred": [...], "responsibilities": [...],
    "other": [...]} — each a list of non-empty lines under that header.
    Everything before the first recognized header goes to "other" (usually
    the intro/company blurb, which is still useful for title guessing)."""
    sections: dict[str, list[str]] = {"required": [], "preferred": [], "responsibilities": [], "other": []}
    current = "other"
    for line in text.splitlines():
        header = _classify_header(line)
        if header is not None:
            current = header
            continue
        if line.strip():
            sections[current].append(line.strip())
    return sections


def guess_title(text: str) -> str | None:
    """The first substantive, short, non-bullet line is almost always the
    job title in a pasted posting — cheap and surprisingly reliable."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) > 80 or stripped.startswith(("-", "•", "*")):
            continue
        return stripped
    return None


def extract_job_skills(sections: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """
    Returns (required_skills, preferred_skills) — canonical taxonomy skill
    names found via the same word-boundary matching used for resumes
    (app/services/resume/scoring.extract_detected_skills), applied
    separately to the required/preferred section text. A skill mentioned
    outside those two sections (e.g. in "responsibilities" or "other") is
    treated as required by default — most postings describe must-have tech
    in the responsibilities prose, not just the requirements bullet list.
    """
    required_text = "\n".join(sections["required"] + sections["other"] + sections["responsibilities"])
    preferred_text = "\n".join(sections["preferred"])

    required = _match_skills(required_text)
    preferred = [s for s in _match_skills(preferred_text) if s not in required]
    return required, preferred


def _match_skills(text: str) -> list[str]:
    found = []
    for skill in all_skill_names():
        pattern = re.compile(r"(?<![\w+#.])" + re.escape(skill) + r"(?![\w+#.])", re.I)
        if pattern.search(text):
            found.append(skill)
    return found


def extract_experience_requirement(text: str) -> str | None:
    match = _EXPERIENCE_YEARS_RE.search(text)
    return match.group(0) if match else None


def extract_education_requirement(text: str) -> str | None:
    match = _DEGREE_RE.search(text)
    return match.group(0) if match else None
