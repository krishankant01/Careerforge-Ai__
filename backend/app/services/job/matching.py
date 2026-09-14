"""
The matching engine (spec section 8).

For every required/preferred skill the job asks for, we classify the
candidate's coverage into exactly one of four categories, in this priority
order (a skill is never double-classified):

  1. exact      — the skill is explicitly listed in the candidate's Skills
                   section (or a known alias of it).
  2. inferred   — not listed as a skill, but the word appears in the
                   candidate's Experience/Projects text: demonstrated
                   through work, not claimed as a skill.
  3. semantic   — a *different* but related skill is present (e.g. job
                   wants TensorFlow, candidate has PyTorch). Detected via a
                   small curated related-skills map; if an AI provider is
                   configured, unresolved skills also get one batched LLM
                   judgment call, which must return a `reasoning` string.
  4. missing    — none of the above found any evidence at all.

Each category carries a fixed confidence weight used for scoring — a
judgment call, not a hidden constant, and it's returned in every response's
score_explanation so it's auditable:

  exact=1.0, inferred=0.85, semantic=0.6, missing=0.0

Coverage score for a set of skills = sum(weight for each skill's match) /
count(skills) * 100 — i.e. the average confidence across all required (or
preferred) skills, not a binary "matched/not" count. Overall compatibility
= required_coverage * 0.7 + preferred_coverage * 0.3 (required matters
more, but preferred still counts).
"""
from app.core.logging import get_logger
from app.services.ai import AIProvider, AIProviderError

logger = get_logger(__name__)

CONFIDENCE_WEIGHTS = {"exact": 1.0, "inferred": 0.85, "semantic": 0.6, "missing": 0.0}

REQUIRED_WEIGHT = 0.7
PREFERRED_WEIGHT = 0.3

# Curated, deliberately small: pairs of skills that are commonly transferable
# within the same category. Symmetric by convention (if A implies some
# familiarity with B, B is listed under A too). This is the deterministic
# stand-in for "semantic similarity" when no AI provider is configured.
RELATED_SKILLS: dict[str, list[str]] = {
    "react": ["vue", "angular"],
    "vue": ["react", "angular"],
    "angular": ["react", "vue"],
    "postgresql": ["mysql", "sqlite"],
    "mysql": ["postgresql", "sqlite"],
    "sqlite": ["postgresql", "mysql"],
    "aws": ["gcp", "azure"],
    "gcp": ["aws", "azure"],
    "azure": ["aws", "gcp"],
    "pytorch": ["tensorflow"],
    "tensorflow": ["pytorch"],
    "docker": ["kubernetes"],
    "kubernetes": ["docker"],
    "flask": ["django", "fastapi", "express"],
    "django": ["flask", "fastapi"],
    "fastapi": ["flask", "django"],
    "express": ["fastapi", "flask", "node.js"],
    "node.js": ["express"],
    "mongodb": ["dynamodb", "postgresql"],
    "dynamodb": ["mongodb"],
    "terraform": ["ci/cd", "github actions"],
    "jenkins": ["github actions", "ci/cd"],
}

_AI_SEMANTIC_SYSTEM_PROMPT = """\
You are comparing a job's required technology against a candidate's actual
skills, to see if any candidate skill is a reasonably close substitute.
You will be given ONE job skill and a list of the candidate's skills.
Respond with ONLY a JSON object (no markdown fences, no commentary):

{
  "match": true or false,
  "matched_skill": "<one skill from the candidate's list, or null>",
  "reasoning": "<1 sentence explaining the connection, or why there isn't one>"
}

Only return match=true if there is a genuine, explainable conceptual
relationship (e.g. same problem domain, similar tool category). Do not
force a match just to be helpful.
"""


def _match_deterministic(job_skill: str, exact: set[str], inferred: set[str]) -> dict | None:
    if job_skill in exact:
        return {
            "match_type": "exact",
            "matched_resume_skill": job_skill,
            "confidence": CONFIDENCE_WEIGHTS["exact"],
            "reasoning": f"'{job_skill}' is explicitly listed in the candidate's Skills section.",
        }
    if job_skill in inferred:
        return {
            "match_type": "inferred",
            "matched_resume_skill": job_skill,
            "confidence": CONFIDENCE_WEIGHTS["inferred"],
            "reasoning": (
                f"'{job_skill}' isn't listed as a skill, but appears in the candidate's "
                "Experience/Projects text — evidence of hands-on use, not just a claim."
            ),
        }
    for related in RELATED_SKILLS.get(job_skill, []):
        if related in exact or related in inferred:
            return {
                "match_type": "semantic",
                "matched_resume_skill": related,
                "confidence": CONFIDENCE_WEIGHTS["semantic"],
                "reasoning": (
                    f"Candidate doesn't show '{job_skill}' directly, but has '{related}', "
                    "a closely related skill in the same category (curated mapping, no AI used)."
                ),
            }
    return None


async def _match_with_ai(
    provider: AIProvider, job_skill: str, candidate_skills: list[str]
) -> dict | None:
    try:
        result = await provider.generate_json(
            system_prompt=_AI_SEMANTIC_SYSTEM_PROMPT,
            user_prompt=f"Job skill: {job_skill}\nCandidate's skills: {', '.join(candidate_skills)}",
            max_tokens=300,
        )
    except AIProviderError as exc:
        logger.info("AI semantic match call failed for %s: %s", job_skill, exc)
        return None

    if not result.get("match") or not result.get("matched_skill"):
        return None

    return {
        "match_type": "semantic",
        "matched_resume_skill": result["matched_skill"],
        "confidence": CONFIDENCE_WEIGHTS["semantic"],
        "reasoning": result.get("reasoning", "Related skill identified by AI review."),
    }


async def classify_skills(
    *,
    required_skills: list[str],
    preferred_skills: list[str],
    exact_skills: set[str],
    inferred_skills: set[str],
    ai_provider: AIProvider | None,
) -> tuple[list[dict], str]:
    """
    Returns (skill_matches, semantic_mode). skill_matches has one entry per
    required+preferred skill (in that order), each with requirement_level
    added. semantic_mode is "ai_assisted" if at least one semantic match
    came from an AI call, else "deterministic".
    """
    all_candidate_skills = sorted(exact_skills | inferred_skills)
    skill_matches: list[dict] = []
    used_ai = False

    for skill, level in [(s, "required") for s in required_skills] + [
        (s, "preferred") for s in preferred_skills
    ]:
        result = _match_deterministic(skill, exact_skills, inferred_skills)

        if result is None and ai_provider is not None and all_candidate_skills:
            result = await _match_with_ai(ai_provider, skill, all_candidate_skills)
            if result is not None:
                used_ai = True

        if result is None:
            result = {
                "match_type": "missing",
                "matched_resume_skill": None,
                "confidence": CONFIDENCE_WEIGHTS["missing"],
                "reasoning": f"No evidence of '{skill}' or a related skill found anywhere in the resume.",
            }

        skill_matches.append({"skill": skill, "requirement_level": level, **result})

    return skill_matches, "ai_assisted" if used_ai else "deterministic"


def score_matches(skill_matches: list[dict]) -> tuple[int, int, int, dict]:
    """Returns (compatibility_score, required_coverage, preferred_coverage, explanation)."""

    def coverage(level: str) -> tuple[int, dict]:
        relevant = [m for m in skill_matches if m["requirement_level"] == level]
        if not relevant:
            return 100, {"skill_count": 0, "note": f"No {level} skills were extracted from this job."}
        avg_confidence = sum(m["confidence"] for m in relevant) / len(relevant)
        score = round(avg_confidence * 100)
        breakdown = {
            "skill_count": len(relevant),
            "exact": sum(1 for m in relevant if m["match_type"] == "exact"),
            "inferred": sum(1 for m in relevant if m["match_type"] == "inferred"),
            "semantic": sum(1 for m in relevant if m["match_type"] == "semantic"),
            "missing": sum(1 for m in relevant if m["match_type"] == "missing"),
        }
        return score, breakdown

    required_score, required_breakdown = coverage("required")
    preferred_score, preferred_breakdown = coverage("preferred")

    overall = round(required_score * REQUIRED_WEIGHT + preferred_score * PREFERRED_WEIGHT)

    explanation = {
        "confidence_weights": CONFIDENCE_WEIGHTS,
        "overall_formula": "overall = required_coverage * 0.7 + preferred_coverage * 0.3",
        "coverage_formula": "coverage = average(confidence of each skill's match category) * 100",
        "required": required_breakdown,
        "preferred": preferred_breakdown,
    }

    return overall, required_score, preferred_score, explanation
