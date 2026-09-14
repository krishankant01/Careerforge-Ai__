"""
The one part of resume analysis that genuinely benefits from an LLM:
judging the *quality* of experience/project descriptions (impact,
specificity, use of metrics) and writing narrative feedback. Regex can find
a bullet point; it can't tell "Responsible for backend stuff" apart from
"Cut API p95 latency 40% by redesigning the caching layer".

Every score this module returns still has to come with a `reasoning`
string that quotes/paraphrases the resume — the prompt requires it, and we
validate it's present before trusting the response (see _validate_result).
If the AI provider is unavailable or misbehaves, we fall back to a
documented heuristic rather than fail the whole analysis; the caller is
told which mode actually produced the result via `analysis_mode`.
"""
from app.services.ai import AIProvider, AIProviderError
from app.core.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a resume reviewer. You will be given the raw text of a resume.
Respond with ONLY a JSON object (no markdown fences, no commentary) with
this exact shape:

{
  "experience_score": <int 0-100>,
  "experience_reasoning": "<1-3 sentences citing specific lines/phrases from the resume>",
  "project_score": <int 0-100>,
  "project_reasoning": "<1-3 sentences citing specific lines/phrases from the resume>",
  "strengths": ["<short phrase>", ...],
  "weaknesses": ["<short phrase>", ...],
  "missing_keywords": ["<keyword commonly expected for this candidate's apparent field>", ...],
  "ats_issues": ["<short phrase describing a formatting/content issue an ATS might struggle with>", ...]
}

Rules:
- Ground every score in something actually present (or absent) in the text.
  Do not invent facts not supported by the resume.
- Distinguish FACT (what the resume states) from INFERENCE (what you
  conclude from it) in your reasoning language where relevant.
- missing_keywords and ats_issues should be genuinely useful, specific
  suggestions — not generic filler.
- Keep every list to at most 6 items.
"""

_REQUIRED_KEYS = {
    "experience_score",
    "experience_reasoning",
    "project_score",
    "project_reasoning",
    "strengths",
    "weaknesses",
    "missing_keywords",
    "ats_issues",
}

# Fields that must be lists — small LLMs (e.g. llama3.2:1b) sometimes
# return a plain string for these instead of a JSON array.
_LIST_FIELDS = ("strengths", "weaknesses", "missing_keywords", "ats_issues")


def _coerce_lists(result: dict) -> dict:
    """
    Ensure every list-typed field actually IS a list.

    Small models frequently emit:
        "ats_issues": "ATS struggle with …"
    instead of:
        "ats_issues": ["ATS struggle with …"]

    We coerce:
      str  → [str]          (wrap single string in a list)
      None → []             (treat null as empty list)
      list → list           (already correct, leave alone)
      other→ []             (safe default)
    """
    for field in _LIST_FIELDS:
        val = result.get(field)
        if isinstance(val, list):
            # Filter out any non-string items to keep the schema clean
            result[field] = [str(item) for item in val if item]
        elif isinstance(val, str) and val.strip():
            # Split on newlines/semicolons in case the model packed multiple
            # items into one string (e.g. "Issue 1; Issue 2")
            parts = [p.strip() for p in val.replace("\n", ";").split(";") if p.strip()]
            result[field] = parts if parts else [val.strip()]
        else:
            result[field] = []
    return result


def _validate_result(result: dict) -> bool:
    if not _REQUIRED_KEYS.issubset(result.keys()):
        return False
    for key in ("experience_score", "project_score"):
        if not isinstance(result[key], int) or not (0 <= result[key] <= 100):
            return False
    return True


async def review_with_ai(provider: AIProvider, resume_text: str) -> dict | None:
    """Returns the parsed+validated AI result, or None if unavailable/invalid
    — callers must have a deterministic fallback ready either way."""
    try:
        result = await provider.generate_json(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=f"Resume text:\n\n{resume_text[:12000]}",
        )
    except AIProviderError as exc:
        logger.info("AI resume review unavailable, falling back to heuristic: %s", exc)
        return None

    if not _validate_result(result):
        logger.warning("AI resume review returned an unexpected shape, discarding")
        return None

    # Coerce list fields AFTER validation of required keys, so we don't
    # discard an otherwise valid response just because one list came back
    # as a string (common with small models).
    result = _coerce_lists(result)

    return result


def review_with_heuristic(sections_by_type: dict[str, list[str]]) -> dict:
    """
    Deterministic fallback used when no AI provider is configured or the AI
    call fails. Proxy formula: score = min(100, entries * 15 + avg_words_per_entry / 4)
    — rewards having multiple entries that are described in some detail,
    without being able to judge the *quality* of that detail the way an LLM
    can. This is intentionally coarser than the AI path, and analysis_mode
    tells the client so.
    """

    def score_bullets(content_blocks: list[str]) -> tuple[int, int, float]:
        if not content_blocks:
            return 0, 0, 0.0
        combined = "\n".join(content_blocks)
        entries = max(1, sum(1 for line in combined.splitlines() if line.strip()))
        word_count = len(combined.split())
        avg_words = word_count / entries if entries else 0
        score = min(100, round(entries * 15 + avg_words / 4))
        return score, entries, round(avg_words, 1)

    exp_score, exp_entries, exp_avg = score_bullets(sections_by_type.get("experience", []))
    proj_score, proj_entries, proj_avg = score_bullets(sections_by_type.get("projects", []))

    return {
        "experience_score": exp_score,
        "experience_reasoning": (
            f"Heuristic (no AI review available): detected {exp_entries} content line(s) "
            f"in the Experience section, averaging {exp_avg} words each. "
            "score = min(100, entries*15 + avg_words/4)."
        ),
        "project_score": proj_score,
        "project_reasoning": (
            f"Heuristic (no AI review available): detected {proj_entries} content line(s) "
            f"in the Projects section, averaging {proj_avg} words each. "
            "score = min(100, entries*15 + avg_words/4)."
        ),
        "strengths": [],
        "weaknesses": [],
        "missing_keywords": [],
        "ats_issues": [],
    }
