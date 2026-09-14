"""
Deterministic skill taxonomy used for the Technical and Skill scores
(app/services/resume/scoring.py). Kept as plain, auditable Python data
rather than an LLM call so those two scores are 100% reproducible: the same
resume text always yields the same score, and every point is traceable to a
specific matched skill.

This is intentionally a starting list, not exhaustive — spec section 9's
Skill Gap Agent (a later phase) will need a much larger, role-aware
taxonomy. Extending this list only ever increases detected skills; it never
needs to change how scoring.py computes scores.
"""

# category -> { skill_name: tier }
# tier 1 = foundational/common, 2 = solidly in-demand, 3 = advanced/high-value
SKILL_TAXONOMY: dict[str, dict[str, int]] = {
    "languages": {
        "python": 2, "javascript": 2, "typescript": 2, "java": 2, "c++": 2,
        "c#": 2, "go": 3, "rust": 3, "ruby": 1, "php": 1, "sql": 1, "kotlin": 2, "swift": 2,
    },
    "frameworks": {
        "react": 2, "vue": 2, "angular": 2, "django": 2, "flask": 1, "fastapi": 3,
        "spring": 2, "express": 1, "next.js": 3, "node.js": 2, ".net": 2,
    },
    "databases": {
        "postgresql": 2, "mysql": 1, "mongodb": 1, "redis": 2, "sqlite": 1,
        "elasticsearch": 3, "dynamodb": 2, "pgvector": 3,
    },
    "cloud_devops": {
        "aws": 2, "gcp": 2, "azure": 2, "docker": 2, "kubernetes": 3,
        "terraform": 3, "ci/cd": 2, "github actions": 2, "jenkins": 1,
    },
    "ai_ml": {
        "machine learning": 3, "langchain": 3, "langgraph": 3, "rag": 3,
        "embeddings": 3, "pytorch": 3, "tensorflow": 2, "llm": 3, "nlp": 2,
    },
    "practices": {
        "rest api": 1, "microservices": 2, "unit testing": 1, "agile": 1,
        "system design": 3, "graphql": 2, "tdd": 2,
    },
}

# Flattened for fast lookup: skill_name -> (category, tier)
_SKILL_LOOKUP: dict[str, tuple[str, int]] = {
    skill: (category, tier)
    for category, skills in SKILL_TAXONOMY.items()
    for skill, tier in skills.items()
}


def lookup_skill(skill_name: str) -> tuple[str, int] | None:
    return _SKILL_LOOKUP.get(skill_name.lower())


def all_skill_names() -> list[str]:
    return list(_SKILL_LOOKUP.keys())


def category_names() -> list[str]:
    return list(SKILL_TAXONOMY.keys())
