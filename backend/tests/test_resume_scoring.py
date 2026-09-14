"""
Pure unit tests for app/services/resume/scoring.py — no DB, no HTTP, no AI
provider. These exist specifically to demonstrate (per the Phase 3 "do not
hardcode scores" requirement) that ATS/Technical/Skill scores are simple,
reproducible functions of the input text.
"""
from app.services.resume.scoring import (
    extract_detected_skills,
    score_ats,
    score_skill_breadth,
    score_technical,
)
from app.services.resume.sections import detect_sections


GOOD_RESUME = """Jane Doe
jane@example.com | 555-123-4567

Summary
Backend engineer.

Skills
Python, FastAPI, PostgreSQL, Docker, AWS, React, Kubernetes

Experience
- Built services in Python and FastAPI
- Deployed with Docker and Kubernetes on AWS

Projects
- A React + FastAPI + PostgreSQL app

Education
B.S. Computer Science
"""


def test_score_ats_rewards_contact_info_and_sections():
    sections = {s.value for s, _, _ in detect_sections(GOOD_RESUME)}
    score, checks = score_ats(GOOD_RESUME, sections)
    assert checks["contact_email"]["passed"] is True
    assert checks["contact_phone"]["passed"] is True
    assert score > 50


def test_score_ats_penalizes_missing_contact_info():
    text = "Skills\nPython\n"
    score, checks = score_ats(text, {"skills"})
    assert checks["contact_email"]["passed"] is False
    assert checks["contact_phone"]["passed"] is False


def test_extract_detected_skills_finds_known_skills_with_evidence():
    detected = extract_detected_skills(GOOD_RESUME)
    names = {d["skill"] for d in detected}
    assert "python" in names
    assert "fastapi" in names
    assert "kubernetes" in names
    python_entry = next(d for d in detected if d["skill"] == "python")
    assert "python" in python_entry["evidence"].lower()


def test_extract_detected_skills_does_not_match_substrings():
    # "javascript" should not be detected inside "typescript", etc.
    text = "I write typescript code."
    detected = extract_detected_skills(text)
    names = {d["skill"] for d in detected}
    assert "javascript" not in names
    assert "typescript" in names


def test_score_technical_scales_with_weighted_skill_points():
    few_skills = [{"skill": "html", "category": "languages", "tier": 1}]
    many_skills = [
        {"skill": "python", "category": "languages", "tier": 2},
        {"skill": "fastapi", "category": "frameworks", "tier": 3},
        {"skill": "kubernetes", "category": "cloud_devops", "tier": 3},
    ]
    score_few, _ = score_technical(few_skills)
    score_many, _ = score_technical(many_skills)
    assert score_many > score_few


def test_score_technical_caps_at_100():
    lots = [{"skill": f"s{i}", "category": "languages", "tier": 3} for i in range(30)]
    score, explanation = score_technical(lots)
    assert score == 100
    assert explanation["weighted_skill_points"] == 90


def test_score_skill_breadth_rewards_category_diversity():
    narrow = [
        {"skill": "python", "category": "languages", "tier": 2},
        {"skill": "java", "category": "languages", "tier": 2},
    ]
    broad = [
        {"skill": "python", "category": "languages", "tier": 2},
        {"skill": "fastapi", "category": "frameworks", "tier": 3},
        {"skill": "postgresql", "category": "databases", "tier": 2},
        {"skill": "aws", "category": "cloud_devops", "tier": 2},
    ]
    narrow_score, _ = score_skill_breadth(narrow)
    broad_score, _ = score_skill_breadth(broad)
    assert broad_score > narrow_score
