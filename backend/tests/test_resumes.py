"""
Phase 3 tests.

Note on background tasks: with httpx's ASGITransport, awaiting
`client.post(...)` does not return until Starlette finishes the entire
ASGI call for that request — including any BackgroundTasks attached to the
response. So by the time an upload call returns here, resume_service's
analysis pipeline has already run to completion (or failure); there's no
need to poll for status in these tests.
"""
import io

import pytest
from docx import Document

from app.services import resume_service
from app.services.ai.base import AIProviderError
from tests.pdf_helper import build_minimal_pdf

SAMPLE_RESUME_LINES = [
    "Jane Doe",
    "jane.doe@example.com | (555) 123-4567",
    "Summary",
    "Backend engineer with 5 years of experience building APIs.",
    "Skills",
    "Python, FastAPI, PostgreSQL, Docker, AWS, React",
    "Experience",
    "- Built a FastAPI service handling 10k requests/sec, reduced latency 40%",
    "- Led migration from monolith to microservices architecture",
    "Projects",
    "- AI Resume Analyzer: FastAPI + PostgreSQL + pgvector RAG pipeline",
    "Education",
    "B.S. Computer Science, State University",
]


def _sample_pdf_bytes() -> bytes:
    return build_minimal_pdf(SAMPLE_RESUME_LINES)


def _sample_docx_bytes() -> bytes:
    doc = Document()
    for line in SAMPLE_RESUME_LINES:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


class FakeAIProvider:
    """Canned AI provider for exercising the ai_assisted path without a real API key."""

    def __init__(self, response: dict | None = None, should_fail: bool = False):
        self._response = response or {
            "experience_score": 82,
            "experience_reasoning": "Mentions a specific latency improvement (40%) with a concrete tech stack.",
            "project_score": 75,
            "project_reasoning": "One well-described project referencing RAG and pgvector.",
            "strengths": ["Quantified impact in experience bullets"],
            "weaknesses": ["Only one project listed"],
            "missing_keywords": ["Kubernetes", "CI/CD"],
            "ats_issues": ["Consider adding a dedicated Certifications section"],
        }
        self._should_fail = should_fail

    async def generate_json(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 2000):
        if self._should_fail:
            raise AIProviderError("simulated provider failure")
        return self._response


async def _complete_background_analysis(resume_id: str) -> None:
    """Run the queued worker explicitly in tests.

    Production returns after storing an upload with ``status=pending`` and
    FastAPI runs the analysis afterward. HTTPX's in-process transport does
    not reliably wait for that task, so tests invoke it before checking the
    final status.
    """
    import uuid

    await resume_service.process_resume_upload(uuid.UUID(resume_id))


# --- Upload + full pipeline -------------------------------------------------


@pytest.mark.asyncio
async def test_upload_pdf_runs_full_pipeline_deterministic(client, auth_headers, monkeypatch):
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: None)

    resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={"file": ("resume.pdf", _sample_pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 201
    resume = resp.json()
    assert resume["status"] == "pending"
    assert resume["file_type"] == "pdf"

    await _complete_background_analysis(resume["id"])

    analysis_resp = await client.get(f"/api/resumes/{resume['id']}/analysis", headers=auth_headers)
    assert analysis_resp.status_code == 200
    analysis = analysis_resp.json()

    assert analysis["analysis_mode"] == "deterministic"
    assert 0 <= analysis["overall_score"] <= 100
    # Skills actually present in SAMPLE_RESUME_LINES should be detected.
    detected_names = {s["skill"] for s in analysis["detected_skills"]}
    assert "python" in detected_names
    assert "fastapi" in detected_names
    assert "postgresql" in detected_names
    # Every score has a traceable explanation, not a bare number.
    assert "ats_score" in analysis["score_explanations"]
    assert "formula" in analysis["score_explanations"]["overall_score"]


@pytest.mark.asyncio
async def test_upload_docx_ai_assisted_mode(client, auth_headers, monkeypatch):
    fake_provider = FakeAIProvider()
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: fake_provider)

    resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={
            "file": (
                "resume.docx",
                _sample_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 201
    resume = resp.json()
    assert resume["status"] == "pending"

    await _complete_background_analysis(resume["id"])

    analysis_resp = await client.get(f"/api/resumes/{resume['id']}/analysis", headers=auth_headers)
    analysis = analysis_resp.json()
    assert analysis["analysis_mode"] == "ai_assisted"
    assert analysis["experience_score"] == 82
    assert analysis["project_score"] == 75
    assert "Kubernetes" in analysis["missing_keywords"]


@pytest.mark.asyncio
async def test_upload_falls_back_to_heuristic_when_ai_call_fails(client, auth_headers, monkeypatch):
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: FakeAIProvider(should_fail=True))

    resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={"file": ("resume.pdf", _sample_pdf_bytes(), "application/pdf")},
    )
    resume = resp.json()
    assert resume["status"] == "pending"

    await _complete_background_analysis(resume["id"])

    analysis_resp = await client.get(f"/api/resumes/{resume['id']}/analysis", headers=auth_headers)
    assert analysis_resp.json()["analysis_mode"] == "deterministic"


# --- Validation errors -------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_extension(client, auth_headers):
    resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={"file": ("resume.txt", b"just some text", "text/plain")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file(client, auth_headers):
    oversized = b"%PDF-" + b"0" * (6 * 1024 * 1024)  # 6MB > 5MB default limit
    resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={"file": ("resume.pdf", oversized, "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_upload_rejects_signature_mismatch(client, auth_headers):
    resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={"file": ("resume.pdf", b"this is not actually a pdf", "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CORRUPT_FILE"


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    resp = await client.post(
        "/api/resumes/upload",
        files={"file": ("resume.pdf", _sample_pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 401


# --- Ownership isolation ------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_resume(client, auth_headers, monkeypatch):
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: None)

    upload_resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={"file": ("resume.pdf", _sample_pdf_bytes(), "application/pdf")},
    )
    resume_id = upload_resp.json()["id"]

    other_register = await client.post(
        "/api/auth/register",
        json={"name": "Other User", "email": "other@example.com", "password": "password1"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    resp = await client.get(f"/api/resumes/{resume_id}", headers=other_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESUME_NOT_FOUND"

    resp = await client.get(f"/api/resumes/{resume_id}/analysis", headers=other_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_resumes_only_returns_own(client, auth_headers, monkeypatch):
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: None)

    await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={"file": ("resume.pdf", _sample_pdf_bytes(), "application/pdf")},
    )

    other_register = await client.post(
        "/api/auth/register",
        json={"name": "Other User", "email": "lister@example.com", "password": "password1"},
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    resp = await client.get("/api/resumes", headers=other_headers)
    assert resp.status_code == 200
    assert resp.json() == []


# --- Extraction failure handling ---------------------------------------------


@pytest.mark.asyncio
async def test_empty_pdf_marks_resume_failed(client, auth_headers, monkeypatch):
    monkeypatch.setattr(resume_service, "get_ai_provider", lambda: None)
    empty_pdf = build_minimal_pdf([])  # valid PDF, zero lines of text

    resp = await client.post(
        "/api/resumes/upload",
        headers=auth_headers,
        files={"file": ("empty.pdf", empty_pdf, "application/pdf")},
    )
    resume = resp.json()
    assert resume["status"] == "pending"

    await _complete_background_analysis(resume["id"])
    detail = await client.get(f"/api/resumes/{resume['id']}", headers=auth_headers)
    assert detail.json()["status"] == "failed"
    assert "no extractable text" in detail.json()["failure_reason"].lower() or "corrupt" in detail.json()["failure_reason"].lower()


# --- Service-layer: analysis-not-ready state ---------------------------------


@pytest.mark.asyncio
async def test_analysis_not_ready_while_pending(db_session):
    import uuid

    from app.core.errors import AnalysisNotReadyError
    from app.models.resume import Resume, ResumeStatus
    from app.models.user import User
    from app.core.security import hash_password

    user = User(name="Pending Tester", email="pending@example.com", hashed_password=hash_password("password1"))
    db_session.add(user)
    await db_session.flush()

    resume = Resume(
        user_id=user.id,
        original_filename="resume.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="/tmp/does-not-matter.pdf",
        status=ResumeStatus.PENDING,
    )
    db_session.add(resume)
    await db_session.commit()

    with pytest.raises(AnalysisNotReadyError):
        await resume_service.get_latest_analysis_for_user(db_session, resume_id=resume.id, user_id=user.id)
