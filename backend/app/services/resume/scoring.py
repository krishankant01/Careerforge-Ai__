"""
Deterministic scoring rubric for ATS, Technical, and Skill scores.

Every function here is pure (text in, number+explanation out) and has no
dependency on the AI provider — this is what makes these three scores
reproducible and unit-testable without mocking anything. Each function
returns (score, explanation) so the "why" is generated alongside the
number, never bolted on afterward (spec section 6: "Explain WHY each score
was given").

None of these functions invent a score out of thin air: every point traces
to something specifically checked against the resume text, listed in the
explanation.
"""
import re
from collections import Counter

from app.services.resume.skills_taxonomy import lookup_skill, category_names

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\-.\s()]{8,}\d)")
_BULLET_RE = re.compile(r"^\s*[-•*]\s+|^\s*\d+[.)]\s+")
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z+#./-]*")

STANDARD_SECTIONS = ["summary", "skills", "education", "experience", "projects", "certifications"]


def score_ats(text: str, detected_section_types: set[str]) -> tuple[int, dict]:
    """
    ATS score out of 100, built from six independently-scored checks:
      - contact info findable (email 15 pts, phone 10 pts)
      - standard sections present (up to 25 pts, proportional to how many
        of the 6 standard sections were detected)
      - healthy length: 250-1200 words (20 pts, partial credit outside that band)
      - uses bullet points, a proxy for scannable formatting (15 pts)
      - low duplicate-line ratio, a proxy for "duplicate information" (15 pts)
    """
    checks: dict[str, dict] = {}
    points = 0

    has_email = bool(_EMAIL_RE.search(text))
    checks["contact_email"] = {"passed": has_email, "points": 15 if has_email else 0}
    points += checks["contact_email"]["points"]

    has_phone = bool(_PHONE_RE.search(text))
    checks["contact_phone"] = {"passed": has_phone, "points": 10 if has_phone else 0}
    points += checks["contact_phone"]["points"]

    sections_found = len(detected_section_types & set(STANDARD_SECTIONS))
    section_points = round((sections_found / len(STANDARD_SECTIONS)) * 25)
    checks["standard_sections"] = {
        "found": sections_found,
        "expected": len(STANDARD_SECTIONS),
        "points": section_points,
    }
    points += section_points

    word_count = len(_WORD_RE.findall(text))
    if 250 <= word_count <= 1200:
        length_points = 20
    elif word_count < 250:
        length_points = max(0, round((word_count / 250) * 20))
    else:  # too long
        length_points = max(0, 20 - round((word_count - 1200) / 200))
    checks["length"] = {"word_count": word_count, "points": length_points}
    points += length_points

    bullet_lines = sum(1 for line in text.splitlines() if _BULLET_RE.match(line))
    bullet_points = 15 if bullet_lines >= 3 else round((bullet_lines / 3) * 15)
    checks["bullet_usage"] = {"bullet_lines": bullet_lines, "points": bullet_points}
    points += bullet_points

    non_blank_lines = [line.strip() for line in text.splitlines() if line.strip()]
    duplicate_ratio = 0.0
    if non_blank_lines:
        counts = Counter(non_blank_lines)
        duplicated = sum(c - 1 for c in counts.values() if c > 1)
        duplicate_ratio = duplicated / len(non_blank_lines)
    duplicate_points = 15 if duplicate_ratio < 0.10 else max(0, round(15 * (1 - duplicate_ratio)))
    checks["duplicate_lines"] = {"ratio": round(duplicate_ratio, 3), "points": duplicate_points}
    points += duplicate_points

    return min(100, points), checks


def skill_appears_in_text(skill: str, text: str) -> bool:
    """Word-boundary, case-insensitive check for one skill in a text
    snippet — the same matching rule as extract_detected_skills, exposed
    standalone so job matching (app/services/job/job_service.py) can check
    a skill against a specific resume *section*'s content rather than the
    whole resume."""
    pattern = re.compile(r"(?<![\w+#.])" + re.escape(skill) + r"(?![\w+#.])", re.I)
    return bool(pattern.search(text))


def extract_detected_skills(text: str) -> list[dict]:
    """
    Matches resume text against SKILL_TAXONOMY using word-boundary,
    case-insensitive matching. Returns one entry per matched skill with the
    line it was found on, so the UI/analysis can show *why* a skill counted
    (spec section 43: "For GitHub analysis, identify repository/file
    evidence" — same principle applied to resumes).
    """
    detected: list[dict] = []
    lines = text.splitlines()

    from app.services.resume.skills_taxonomy import all_skill_names

    for skill in all_skill_names():
        pattern = re.compile(r"(?<![\w+#.])" + re.escape(skill) + r"(?![\w+#.])", re.I)
        for line_no, line in enumerate(lines):
            if pattern.search(line):
                category, tier = lookup_skill(skill)
                detected.append(
                    {
                        "skill": skill,
                        "category": category,
                        "tier": tier,
                        "evidence": line.strip()[:200],
                        "line_number": line_no + 1,
                    }
                )
                break  # one piece of evidence per skill is enough

    return detected


def score_technical(detected_skills: list[dict]) -> tuple[int, dict]:
    """
    Technical score out of 100: sum of each detected skill's tier
    (1/2/3 points), scaled against a documented ceiling of 40 weighted
    points = 100. The ceiling is a judgment call (roughly "15-20 solid
    skills across categories"), not a hidden constant — it's returned in
    the explanation so it's auditable.
    """
    CEILING = 40
    weighted_total = sum(skill["tier"] for skill in detected_skills)
    score = min(100, round((weighted_total / CEILING) * 100))
    explanation = {
        "weighted_skill_points": weighted_total,
        "ceiling_for_100": CEILING,
        "skills_counted": len(detected_skills),
        "formula": "score = min(100, round(weighted_points / ceiling * 100))",
    }
    return score, explanation


def score_skill_breadth(detected_skills: list[dict]) -> tuple[int, dict]:
    """
    Skill score out of 100: how many of the 6 taxonomy categories
    (languages, frameworks, databases, cloud/devops, ai/ml, practices) have
    at least one detected skill. Rewards breadth across a stack rather than
    depth in one area, which the Technical score already captures.
    """
    categories_present = {skill["category"] for skill in detected_skills}
    total_categories = len(category_names())
    score = round((len(categories_present) / total_categories) * 100)
    explanation = {
        "categories_present": sorted(categories_present),
        "categories_total": total_categories,
        "formula": "score = round(categories_present / categories_total * 100)",
    }
    return score, explanation
