"""
Job Description Analyzer + Matching orchestration (spec sections 7, 8, 44).

Mirrors resume_service.py's shape on purpose: create_job / process_job_parsing
follow the same "return fast, finish in a background task, poll status"
pattern as save_uploaded_resume / process_resume_upload from Phase 3. Every
read function takes user_id and filters by it — ownership is enforced here,
not in the route layer (spec section 44).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.errors import JobNotFoundError, JobNotReadyError, ResumeNotReadyForMatchError
from app.core.logging import get_logger
from app.models.job import Job, JobMatch, JobStatus
from app.models.resume import ResumeStatus, SectionType
from app.services import resume_service
from app.services.ai import get_ai_provider
from app.services.job import ai_parsing, matching, parsing
from app.services.resume.scoring import skill_appears_in_text

logger = get_logger(__name__)


async def create_job(db: AsyncSession, *, user_id: uuid.UUID, raw_description: str) -> Job:
    job = Job(user_id=user_id, raw_description=raw_description, status=JobStatus.PENDING)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def process_job_parsing(job_id: uuid.UUID) -> None:
    """Background task — opens its own session, same reasoning as
    resume_service.process_resume_upload (the request's session is already
    closed by the time this runs)."""
    async with database.AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        if job is None:
            logger.warning("process_job_parsing: job %s no longer exists", job_id)
            return

        try:
            job.status = JobStatus.PROCESSING
            await db.commit()

            sections = parsing.split_job_sections(job.raw_description)
            det_required, det_preferred = parsing.extract_job_skills(sections)

            provider = get_ai_provider()
            ai_result = await ai_parsing.parse_with_ai(provider, job.raw_description) if provider else None

            if ai_result is not None:
                job.title = ai_result["title"]
                job.company = ai_result["company"]
                job.responsibilities = ai_result["responsibilities"]
                job.required_skills = ai_result["required_skills"] or det_required
                job.preferred_skills = ai_result["preferred_skills"] or det_preferred
                job.experience_requirement = ai_result["experience_requirement"]
                job.education_requirement = ai_result["education_requirement"]
                job.parse_mode = "ai_assisted"
            else:
                job.title = parsing.guess_title(job.raw_description)
                job.company = None
                job.responsibilities = sections["responsibilities"][:8]
                job.required_skills = det_required
                job.preferred_skills = det_preferred
                job.experience_requirement = parsing.extract_experience_requirement(job.raw_description)
                job.education_requirement = parsing.extract_education_requirement(job.raw_description)
                job.parse_mode = "deterministic"

            job.status = JobStatus.COMPLETED
            job.failure_reason = None
            await db.commit()

        except Exception as exc:  # noqa: BLE001 - must not crash the worker
            logger.exception("Job parsing failed for %s", job_id)
            job.status = JobStatus.FAILED
            job.failure_reason = f"Unexpected error during parsing: {exc}"[:500]
            await db.commit()


async def get_job_for_user(db: AsyncSession, *, job_id: uuid.UUID, user_id: uuid.UUID) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError()
    return job


async def list_jobs_for_user(db: AsyncSession, *, user_id: uuid.UUID) -> list[Job]:
    result = await db.execute(
        select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())


async def run_match(
    db: AsyncSession, *, job_id: uuid.UUID, resume_id: uuid.UUID, user_id: uuid.UUID
) -> JobMatch:
    """
    The actual matching pipeline. Runs synchronously within the request —
    unlike resume/job parsing, this is at most one batch of small AI calls
    (one per unresolved skill) against data that's already fully processed,
    so it doesn't need a background task.
    """
    job = await get_job_for_user(db, job_id=job_id, user_id=user_id)
    if job.status != JobStatus.COMPLETED:
        raise JobNotReadyError(job.status.value)

    # Ownership + readiness for the resume side of the match.
    resume = await resume_service.get_resume_with_sections(db, resume_id=resume_id, user_id=user_id)
    if resume.status != ResumeStatus.COMPLETED:
        raise ResumeNotReadyForMatchError(resume.status.value)
    analysis = await resume_service.get_latest_analysis_for_user(
        db, resume_id=resume_id, user_id=user_id
    )

    # Split the candidate's already-detected skills into "exact" (found in
    # a Skills-type section) vs "inferred" (found only in Experience/
    # Projects) — see matching.py's module docstring for why this split
    # matters. A skill detected somewhere else (e.g. Summary) defaults to
    # exact, since the candidate still explicitly used the word.
    skills_text = "\n".join(s.content for s in resume.sections if s.section_type == SectionType.SKILLS)
    exp_proj_text = "\n".join(
        s.content for s in resume.sections if s.section_type in (SectionType.EXPERIENCE, SectionType.PROJECTS)
    )

    exact_skills: set[str] = set()
    inferred_skills: set[str] = set()
    for detected in analysis.detected_skills:
        skill = detected["skill"]
        if skills_text and skill_appears_in_text(skill, skills_text):
            exact_skills.add(skill)
        elif exp_proj_text and skill_appears_in_text(skill, exp_proj_text):
            inferred_skills.add(skill)
        else:
            exact_skills.add(skill)  # found elsewhere (e.g. Summary) — treat as an explicit claim

    ai_provider = get_ai_provider()
    skill_matches, semantic_mode = await matching.classify_skills(
        required_skills=job.required_skills or [],
        preferred_skills=job.preferred_skills or [],
        exact_skills=exact_skills,
        inferred_skills=inferred_skills,
        ai_provider=ai_provider,
    )
    overall, required_score, preferred_score, explanation = matching.score_matches(skill_matches)

    match = JobMatch(
        job_id=job.id,
        resume_id=resume.id,
        compatibility_score=overall,
        required_coverage_score=required_score,
        preferred_coverage_score=preferred_score,
        skill_matches=skill_matches,
        score_explanation=explanation,
        semantic_mode=semantic_mode,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


async def list_matches_for_resume(
    db: AsyncSession, *, resume_id: uuid.UUID, user_id: uuid.UUID
) -> list[JobMatch]:
    """Powers the job-comparison dashboard: every match run for one resume,
    across all jobs, newest first. Ownership is enforced by first resolving
    the resume through resume_service (raises ResumeNotFoundError if it
    isn't the caller's)."""
    await resume_service.get_resume_for_user(db, resume_id=resume_id, user_id=user_id)

    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(JobMatch)
        .options(selectinload(JobMatch.job))
        .join(Job, JobMatch.job_id == Job.id)
        .where(JobMatch.resume_id == resume_id, Job.user_id == user_id)
        .order_by(JobMatch.created_at.desc())
    )
    return list(result.scalars().all())
