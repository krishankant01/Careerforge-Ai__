"""
Phase 4 tests. Background tasks (job parsing, and resume analysis reused
from Phase 3) complete synchronously within the ASGI call, same as noted in
tests/test_resumes.py — no polling needed.
"""
import pytest
from docx import Document
import io
import uuid

from app.services import job_service, resume_service
from app.services.ai.base import AIProviderError

SAMPLE_JOB_DESCRIPTION = """Senior Backend Engineer

We are looking for an experienced backend engineer to join our platform team.

Requirements
Python, FastAPI, Docker, GraphQL
3+ years of experience
Bachelor's degree in Computer Science or related field

Responsibilities
- Design and build REST APIs
- Own services in production

Preferred Qualifications
Kubernetes, Vue
"""

SAMPLE_RESUME_LINES = [
    "Jane Doe",
    "jane@example.com | 555-123-4567",
    "Skills",
    "Python, FastAPI, PostgreSQL, React",
    "Experience",
    "- Deployed services using Docker and Kubernetes on AWS",
    "- Built REST APIs with FastAPI handling 10k req/sec",
    "Projects",
    "- Internal tool built with FastAPI and PostgreSQL",
    "Education",
    "B.S. Computer Science",
]


def _sample_docx_bytes(lines: list[str]) -> bytes:
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


class DispatchingFakeAIProvider:
    """Routes to a different canned response depending on which system
    prompt is used — job parsing and semantic matching share the AIProvider
    interface but need very different responses."""

    def __init__(self, job_parse_response: dict | None = None, semantic_response: dict | None = None):
        self.job_parse_response = job_parse_response
        self.semantic_response = semantic_response

    async def generate_json(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 2000):
        if "job description parser" in system_prompt and self.job_parse_response is not None:
            return self.job_parse_response
        if "comparing a job's required technology" in system_prompt:
            if self.semantic_response is None:
                raise AIProviderError("no semantic response configured")
            return self.semantic_response
        raise AIProviderError("unexpected prompt in test double")


async def _upload_and_complete_resume(client, auth_headers, monkeypatch, lines=None):
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: None)
    resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={
            "file": (
                "resume.docx",
                _sample_docx_bytes(lines or SAMPLE_RESUME_LINES),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 201
    resume = resp.json()
    await resume_service.process_resume_upload(uuid.UUID(resume["id"]))
    return resume


async def _complete_job_parsing(job_id: str) -> None:
    """Run the queued parser explicitly in tests.

    In the application the API deliberately responds with a pending job and
    parses it in a background task. HTTPX's ASGI transport doesn't reliably
    wait for that task, so tests invoke the worker before inspecting output.
    """
    await job_service.process_job_parsing(uuid.UUID(job_id))


# --- Job creation / parsing --------------------------------------------------


@pytest.mark.asyncio
async def test_create_job_deterministic_parsing(client, auth_headers, monkeypatch):
    monkeypatch.setattr(job_service, "get_ai_provider", lambda: None)

    resp = await client.post(
        "/api/jobs", headers=auth_headers, json={"raw_description": SAMPLE_JOB_DESCRIPTION}
    )
    assert resp.status_code == 201
    job = resp.json()
    assert job["status"] == "pending"

    await _complete_job_parsing(job["id"])
    job = (await client.get(f"/api/jobs/{job['id']}", headers=auth_headers)).json()
    assert job["status"] == "completed"
    assert job["parse_mode"] == "deterministic"
    assert job["title"] == "Senior Backend Engineer"
    assert set(job["required_skills"]) >= {"python", "fastapi", "docker", "graphql"}
    assert "kubernetes" in job["preferred_skills"]
    assert "vue" in job["preferred_skills"]
    assert job["experience_requirement"] is not None
    assert job["education_requirement"] is not None


@pytest.mark.asyncio
async def test_create_job_ai_assisted_parsing(client, auth_headers, monkeypatch):
    fake = DispatchingFakeAIProvider(
        job_parse_response={
            "title": "Staff Backend Engineer",
            "company": "Acme Corp",
            "responsibilities": ["Design APIs"],
            "required_skills": ["python", "fastapi"],
            "preferred_skills": ["kubernetes"],
            "experience_requirement": "5+ years",
            "education_requirement": None,
        }
    )
    monkeypatch.setattr(job_service, "get_ai_provider", lambda: fake)

    resp = await client.post(
        "/api/jobs", headers=auth_headers, json={"raw_description": SAMPLE_JOB_DESCRIPTION}
    )
    job = resp.json()
    await _complete_job_parsing(job["id"])
    job = (await client.get(f"/api/jobs/{job['id']}", headers=auth_headers)).json()
    assert job["parse_mode"] == "ai_assisted"
    assert job["title"] == "Staff Backend Engineer"
    assert job["company"] == "Acme Corp"
    assert job["required_skills"] == ["python", "fastapi"]


@pytest.mark.asyncio
async def test_create_job_requires_auth(client):
    resp = await client.post("/api/jobs", json={"raw_description": SAMPLE_JOB_DESCRIPTION})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_job_rejects_too_short_description(client, auth_headers):
    resp = await client.post("/api/jobs", headers=auth_headers, json={"raw_description": "too short"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_job_ownership_isolation(client, auth_headers, monkeypatch):
    monkeypatch.setattr(job_service, "get_ai_provider", lambda: None)

    create_resp = await client.post(
        "/api/jobs", headers=auth_headers, json={"raw_description": SAMPLE_JOB_DESCRIPTION}
    )
    job_id = create_resp.json()["id"]

    other = await client.post(
        "/api/auth/register",
        json={"name": "Other", "email": "otherjobs@example.com", "password": "password1"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    resp = await client.get(f"/api/jobs/{job_id}", headers=other_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"


# --- Matching: the four categories ------------------------------------------


@pytest.mark.asyncio
async def test_match_categorizes_exact_inferred_semantic_missing(client, auth_headers, monkeypatch):
    monkeypatch.setattr(job_service, "get_ai_provider", lambda: None)
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: None)

    resume = await _upload_and_complete_resume(client, auth_headers, monkeypatch)

    job_resp = await client.post(
        "/api/jobs", headers=auth_headers, json={"raw_description": SAMPLE_JOB_DESCRIPTION}
    )
    job = job_resp.json()
    await _complete_job_parsing(job["id"])

    match_resp = await client.post(
        f"/api/jobs/{job['id']}/match", headers=auth_headers, json={"resume_id": resume["id"]}
    )
    assert match_resp.status_code == 200
    match = match_resp.json()
    assert match["semantic_mode"] == "deterministic"

    by_skill = {m["skill"]: m for m in match["skill_matches"]}

    # python, fastapi: listed directly in the resume's Skills section
    assert by_skill["python"]["match_type"] == "exact"
    assert by_skill["fastapi"]["match_type"] == "exact"

    # docker: only appears in Experience narrative, not Skills -> inferred
    assert by_skill["docker"]["match_type"] == "inferred"

    # graphql: not present anywhere in the resume, no related-skill mapping -> missing
    assert by_skill["graphql"]["match_type"] == "missing"
    assert by_skill["graphql"]["matched_resume_skill"] is None

    # kubernetes (preferred): only in Experience narrative -> inferred
    assert by_skill["kubernetes"]["match_type"] == "inferred"
    assert by_skill["kubernetes"]["requirement_level"] == "preferred"

    # vue (preferred): not in resume at all, but resume has "react" and
    # RELATED_SKILLS maps vue -> react -> semantic match
    assert by_skill["vue"]["match_type"] == "semantic"
    assert by_skill["vue"]["matched_resume_skill"] == "react"

    # Every match has a human-readable reasoning string.
    assert all(m["reasoning"] for m in match["skill_matches"])

    # Scores are in sane ranges given 2/4 required exact+inferred and one
    # missing, 1 inferred + 1 semantic preferred — not asserting exact
    # numbers here to avoid coupling the test to float-rounding edge cases.
    assert 50 <= match["required_coverage_score"] <= 80
    assert 55 <= match["preferred_coverage_score"] <= 85
    assert 0 <= match["compatibility_score"] <= 100
    assert match["score_explanation"]["confidence_weights"]["exact"] == 1.0
    assert match["score_explanation"]["confidence_weights"]["missing"] == 0.0


@pytest.mark.asyncio
async def test_match_semantic_via_ai_when_no_curated_mapping_exists(client, auth_headers, monkeypatch):
    # "rust" has no curated RELATED_SKILLS entry, so this can only match
    # semantically via the AI path.
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: None)

    job_text = SAMPLE_JOB_DESCRIPTION.replace("Kubernetes, Vue", "Rust, Vue")
    fake = DispatchingFakeAIProvider(
        semantic_response={
            "match": True,
            "matched_skill": "go",
            "reasoning": "Both are modern, statically-typed systems languages; Go experience transfers reasonably well to Rust.",
        }
    )
    monkeypatch.setattr(job_service, "get_ai_provider", lambda: fake)

    resume = await _upload_and_complete_resume(
        client,
        auth_headers,
        monkeypatch,
        lines=SAMPLE_RESUME_LINES[:3] + ["Python, FastAPI, PostgreSQL, React, Go"] + SAMPLE_RESUME_LINES[4:],
    )

    job_resp = await client.post("/api/jobs", headers=auth_headers, json={"raw_description": job_text})
    job = job_resp.json()
    await _complete_job_parsing(job["id"])
    job = (await client.get(f"/api/jobs/{job['id']}", headers=auth_headers)).json()
    assert "rust" in job["preferred_skills"]

    match_resp = await client.post(
        f"/api/jobs/{job['id']}/match", headers=auth_headers, json={"resume_id": resume["id"]}
    )
    match = match_resp.json()
    assert match["semantic_mode"] == "ai_assisted"

    by_skill = {m["skill"]: m for m in match["skill_matches"]}
    assert by_skill["rust"]["match_type"] == "semantic"
    assert by_skill["rust"]["matched_resume_skill"] == "go"


@pytest.mark.asyncio
async def test_match_requires_completed_job(db_session):
    import uuid as uuid_module

    from app.core.errors import JobNotReadyError
    from app.core.security import hash_password
    from app.models.job import Job, JobStatus
    from app.models.user import User

    user = User(name="Pending", email="pendingjob@example.com", hashed_password=hash_password("password1"))
    db_session.add(user)
    await db_session.flush()

    job = Job(user_id=user.id, raw_description=SAMPLE_JOB_DESCRIPTION, status=JobStatus.PENDING)
    db_session.add(job)
    await db_session.commit()

    with pytest.raises(JobNotReadyError):
        await job_service.run_match(
            db_session, job_id=job.id, resume_id=uuid_module.uuid4(), user_id=user.id
        )


# --- Comparison dashboard -----------------------------------------------------


@pytest.mark.asyncio
async def test_comparison_dashboard_lists_matches_with_job_context(client, auth_headers, monkeypatch):
    monkeypatch.setattr(job_service, "get_ai_provider", lambda: None)
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: None)

    resume = await _upload_and_complete_resume(client, auth_headers, monkeypatch)

    job_resp = await client.post(
        "/api/jobs", headers=auth_headers, json={"raw_description": SAMPLE_JOB_DESCRIPTION}
    )
    job = job_resp.json()
    await _complete_job_parsing(job["id"])
    await client.post(
        f"/api/jobs/{job['id']}/match", headers=auth_headers, json={"resume_id": resume["id"]}
    )

    resp = await client.get(f"/api/resumes/{resume['id']}/matches", headers=auth_headers)
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) == 1
    assert matches[0]["job_title"] == "Senior Backend Engineer"
    assert matches[0]["job_id"] == job["id"]
