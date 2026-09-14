"""
AI-assisted job parsing. Deterministic regex parsing (parsing.py) is
reasonably reliable for skills (word matching is word matching) but weak
at title/company detection and responsibility summarization for oddly
formatted postings. When an AI provider is configured, we let it do that
part — but we NEVER let it invent skills outside the taxonomy: the AI's
required/preferred skill lists are intersected with the same taxonomy
skill_names as the deterministic path, keeping the two extraction modes
comparable for scoring purposes (see job_service.OVERALL structure).
"""
from app.core.logging import get_logger
from app.services.ai import AIProvider, AIProviderError
from app.services.resume.skills_taxonomy import all_skill_names

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a job description parser. You will be given the raw text of a job
posting. Respond with ONLY a JSON object (no markdown fences, no
commentary) with this exact shape:

{
  "title": "<job title, or null if not clearly stated>",
  "company": "<company name, or null if not stated>",
  "responsibilities": ["<short phrase>", ...],
  "required_skills": ["<skill name>", ...],
  "preferred_skills": ["<skill name>", ...],
  "experience_requirement": "<e.g. '3+ years', or null>",
  "education_requirement": "<e.g. \\"Bachelor's degree\\", or null>"
}

Rules:
- required_skills and preferred_skills must be skill/technology names only
  (e.g. "Python", "AWS", "System Design") — not soft skills, not full
  sentences.
- A skill mentioned in the main requirements or responsibilities counts as
  required. Only skills explicitly under a "nice to have" / "preferred" /
  "bonus" heading count as preferred.
- Keep responsibilities to at most 8 short phrases.
- Use null (not empty string) for anything not stated in the text.
"""

_REQUIRED_KEYS = {
    "title",
    "company",
    "responsibilities",
    "required_skills",
    "preferred_skills",
    "experience_requirement",
    "education_requirement",
}


def _normalize_to_taxonomy(skills: list) -> list[str]:
    """Keeps only AI-suggested skills that also exist in our taxonomy (case-
    insensitive), so ai_assisted and deterministic parse results stay on the
    same vocabulary — matching.py can't compare skills across two different
    naming schemes."""
    taxonomy = set(all_skill_names())
    normalized = []
    for skill in skills:
        if isinstance(skill, str) and skill.lower() in taxonomy:
            normalized.append(skill.lower())
    return normalized


async def parse_with_ai(provider: AIProvider, job_text: str) -> dict | None:
    try:
        result = await provider.generate_json(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=f"Job description:\n\n{job_text[:12000]}",
        )
    except AIProviderError as exc:
        logger.info("AI job parsing unavailable, falling back to heuristic: %s", exc)
        return None

    if not _REQUIRED_KEYS.issubset(result.keys()):
        logger.warning("AI job parse returned an unexpected shape, discarding")
        return None

    result["required_skills"] = _normalize_to_taxonomy(result.get("required_skills") or [])
    result["preferred_skills"] = [
        s for s in _normalize_to_taxonomy(result.get("preferred_skills") or [])
        if s not in result["required_skills"]
    ]
    return result
