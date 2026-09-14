"""Job Description Analyzer + Matching endpoints (spec section 27)."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.job import JobCreateRequest, JobMatchRead, JobMatchRequest, JobRead
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRead, status_code=201)
async def create_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRead:
    job = await job_service.create_job(
        db, user_id=current_user.id, raw_description=payload.raw_description
    )
    # Same pattern as resume upload (Phase 3): return immediately with
    # status=pending, parse in the background, poll GET /jobs/{id}.
    background_tasks.add_task(job_service.process_job_parsing, job.id)
    return job


@router.get("", response_model=list[JobRead])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobRead]:
    return await job_service.list_jobs_for_user(db, user_id=current_user.id)


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRead:
    return await job_service.get_job_for_user(db, job_id=job_id, user_id=current_user.id)


@router.post("/{job_id}/match", response_model=JobMatchRead)
async def match_job(
    job_id: uuid.UUID,
    payload: JobMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobMatchRead:
    return await job_service.run_match(
        db, job_id=job_id, resume_id=payload.resume_id, user_id=current_user.id
    )
