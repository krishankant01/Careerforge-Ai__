"""
Resume Intelligence orchestration (spec sections 6, 26, 44).

Two halves, run at different times:

  1. `save_uploaded_resume` — runs inside the request. Validates the file,
     stores it, creates the Resume row (status=pending), returns fast.
  2. `process_resume_upload` — runs afterward via FastAPI BackgroundTasks
     (see app/api/resumes.py). Does the actual extraction/scoring/AI work
     and updates the row's status as it goes.

Splitting it this way means the upload endpoint responds in milliseconds
regardless of how slow text extraction or the AI call turns out to be — the
frontend polls GET /resumes/{id} for status instead of holding a connection
open.

Every read/list function here takes `user_id` and filters by it — the
route layer never queries Resume directly, so there's exactly one place
ownership can be forgotten, and it isn't here.
"""
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core import database
from app.core.errors import (
    AnalysisNotReadyError,
    CorruptFileError,
    ResumeNotFoundError,
)
from app.core.logging import get_logger
from app.models.resume import Resume, ResumeAnalysis, ResumeSection, ResumeStatus
from app.services.ai import get_ai_provider
from app.services.resume import ai_review
from app.services.resume.extraction import extract_text
from app.services.resume.file_validation import validate_extension, validate_signature, validate_size
from app.services.resume.scoring import (
    extract_detected_skills,
    score_ats,
    score_skill_breadth,
    score_technical,
)
from app.services.resume.sections import detect_sections

logger = get_logger(__name__)
settings = get_settings()


def _as_list(value) -> list:
    """
    Coerce *value* to a list.

    Small LLMs (e.g. llama3.2:1b) sometimes return list-typed schema fields
    as plain strings instead of JSON arrays, which causes a
    ResponseValidationError.  This helper normalises the value so the rest of
    the pipeline always sees a proper list.

      list  → list   (untouched)
      str   → [str]  (wrap in list; split on '; ' / newlines for multi-items)
      None  → []
      other → []
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        parts = [p.strip() for p in value.replace("\n", ";").split(";") if p.strip()]
        return parts or [value.strip()]
    return []


# Weights for the overall score — a fixed, documented formula, never a
# separate AI guess. Technical + Skill together (50%) reflect "can this
# candidate do the job on paper"; Experience + Project (40%) reflect
# "has this candidate actually done it"; ATS (10%) is a smaller weight
# because it measures the resume's *format*, not the candidate.
OVERALL_SCORE_WEIGHTS = {
    "technical_score": 0.30,
    "skill_score": 0.20,
    "project_score": 0.20,
    "experience_score": 0.20,
    "ats_score": 0.10,
}


async def save_uploaded_resume(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> Resume:
    """Validates and stores the uploaded file, creates the Resume row.
    Does NOT extract or score anything — that happens in the background."""
    file_type = validate_extension(filename, settings.ALLOWED_RESUME_EXTENSIONS)
    validate_size(len(content), settings.MAX_RESUME_FILE_SIZE_MB)
    if not validate_signature(content, file_type):
        raise CorruptFileError()

    resume_id = uuid.uuid4()
    user_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)

    # Server-generated filename only — the user's original name is stored
    # separately for display and never touches the filesystem path, which
    # is what prevents path traversal (spec section 29) regardless of what
    # the client sends as a filename.
    storage_path = os.path.join(user_dir, f"{resume_id}.{file_type}")
    with open(storage_path, "wb") as f:
        f.write(content)

    resume = Resume(
        id=resume_id,
        user_id=user_id,
        original_filename=os.path.basename(filename)[:255],
        file_type=file_type,
        file_size_bytes=len(content),
        storage_path=storage_path,
        status=ResumeStatus.PENDING,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


async def process_resume_upload(resume_id: uuid.UUID) -> None:
    """
    The background pipeline. Opens its OWN db session (the request's session
    is already closed by the time BackgroundTasks runs) so this must not
    receive a session from the caller.
    """
    async with database.AsyncSessionLocal() as db:
        resume = await db.get(Resume, resume_id)
        if resume is None:
            logger.warning("process_resume_upload: resume %s no longer exists", resume_id)
            return

        try:
            resume.status = ResumeStatus.PROCESSING
            await db.commit()

            text = extract_text(resume.storage_path, resume.file_type)
            if not text.strip():
                raise CorruptFileError()

            resume.raw_text = text
            detected = detect_sections(text)

            # Replace any sections from a previous analysis run.
            await db.execute(
                ResumeSection.__table__.delete().where(ResumeSection.resume_id == resume.id)
            )
            sections_by_type: dict[str, list[str]] = {}
            for section_type, order_index, content in detected:
                db.add(
                    ResumeSection(
                        resume_id=resume.id,
                        section_type=section_type,
                        order_index=order_index,
                        content=content,
                    )
                )
                sections_by_type.setdefault(section_type.value, []).append(content)

            analysis = await _run_analysis(text, sections_by_type)
            analysis.resume_id = resume.id
            db.add(analysis)

            resume.status = ResumeStatus.COMPLETED
            resume.failure_reason = None
            await db.commit()

            # Trigger RAG reindex so the newly uploaded resume is searchable immediately
            from app.rag.pipeline import rag_pipeline
            await rag_pipeline.reindex_user(db, resume.user_id)

        except CorruptFileError:
            resume.status = ResumeStatus.FAILED
            resume.failure_reason = "Could not extract text from this file. It may be corrupt, empty, or image-only (scanned) with no selectable text."
            await db.commit()
        except Exception as exc:  # noqa: BLE001 - last line of defense; must not crash the worker
            logger.exception("Resume analysis failed for %s", resume_id)
            resume.status = ResumeStatus.FAILED
            resume.failure_reason = f"Unexpected error during analysis: {exc}"[:500]
            await db.commit()


async def _run_analysis(text: str, sections_by_type: dict[str, list[str]]) -> ResumeAnalysis:
    detected_section_types = set(sections_by_type.keys())

    ats_score, ats_checks = score_ats(text, detected_section_types)
    detected_skills = extract_detected_skills(text)
    technical_score, technical_explanation = score_technical(detected_skills)
    skill_score, skill_explanation = score_skill_breadth(detected_skills)

    provider = get_ai_provider()
    ai_result = None
    if provider is not None:
        ai_result = await ai_review.review_with_ai(provider, text)

    analysis_mode = "ai_assisted" if ai_result is not None else "deterministic"
    if ai_result is None:
        ai_result = ai_review.review_with_heuristic(sections_by_type)

    scores = {
        "ats_score": ats_score,
        "technical_score": technical_score,
        "skill_score": skill_score,
        "experience_score": ai_result["experience_score"],
        "project_score": ai_result["project_score"],
    }
    overall_score = round(
        sum(scores[key] * weight for key, weight in OVERALL_SCORE_WEIGHTS.items())
    )

    score_explanations = {
        "overall_score": {
            "weights": OVERALL_SCORE_WEIGHTS,
            "formula": "overall = sum(sub_score * weight for each sub_score)",
            "inputs": scores,
        },
        "ats_score": ats_checks,
        "technical_score": technical_explanation,
        "skill_score": skill_explanation,
        "experience_score": ai_result["experience_reasoning"],
        "project_score": ai_result["project_reasoning"],
    }

    return ResumeAnalysis(
        overall_score=overall_score,
        ats_score=ats_score,
        technical_score=technical_score,
        experience_score=ai_result["experience_score"],
        project_score=ai_result["project_score"],
        skill_score=skill_score,
        score_explanations=score_explanations,
        detected_skills=detected_skills,
        missing_keywords=_as_list(ai_result.get("missing_keywords", [])),
        ats_issues=_as_list(ai_result.get("ats_issues", [])),
        strengths=_as_list(ai_result.get("strengths", [])),
        weaknesses=_as_list(ai_result.get("weaknesses", [])),
        analysis_mode=analysis_mode,
    )


async def get_resume_for_user(db: AsyncSession, *, resume_id: uuid.UUID, user_id: uuid.UUID) -> Resume:
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise ResumeNotFoundError()
    return resume


async def list_resumes_for_user(db: AsyncSession, *, user_id: uuid.UUID) -> list[Resume]:
    result = await db.execute(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
    )
    return list(result.scalars().all())


async def get_resume_with_sections(
    db: AsyncSession, *, resume_id: uuid.UUID, user_id: uuid.UUID
) -> Resume:
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Resume)
        .options(selectinload(Resume.sections))
        .where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise ResumeNotFoundError()
    resume.sections.sort(key=lambda s: s.order_index)
    return resume


async def get_latest_analysis_for_user(
    db: AsyncSession, *, resume_id: uuid.UUID, user_id: uuid.UUID
) -> ResumeAnalysis:
    # Ownership check happens via get_resume_for_user first — a 404 here
    # is indistinguishable from "not yours", by design (spec section 44).
    resume = await get_resume_for_user(db, resume_id=resume_id, user_id=user_id)

    if resume.status != ResumeStatus.COMPLETED:
        raise AnalysisNotReadyError(resume.status.value)

    result = await db.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.resume_id == resume.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        # Shouldn't happen if status==COMPLETED, but don't 500 if it does.
        raise AnalysisNotReadyError(resume.status.value)
    return analysis
