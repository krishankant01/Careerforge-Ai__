"""Resume Intelligence endpoints (spec section 27)."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.job import JobMatchRead, JobMatchWithJobRead
from app.schemas.resume import ResumeAnalysisRead, ResumeDetailRead, ResumeRead
from app.services import job_service, resume_service

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeRead, status_code=201)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeRead:
    # Validate MIME type
    allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    if file.content_type not in allowed_types:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF and DOCX are allowed.")
        
    content = await file.read()
    
    # Validate size (5MB max)
    if len(content) > 5 * 1024 * 1024:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 5MB.")

    resume = await resume_service.save_uploaded_resume(
        db, user_id=current_user.id, filename=file.filename or "resume", content=content
    )
    # Returns immediately with status=pending; extraction/scoring happens
    # after the response is sent (see resume_service.process_resume_upload
    # for why it opens its own DB session rather than reusing this one).
    background_tasks.add_task(resume_service.process_resume_upload, resume.id)
    return resume


@router.get("", response_model=list[ResumeRead])
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeRead]:
    return await resume_service.list_resumes_for_user(db, user_id=current_user.id)


@router.get("/{resume_id}", response_model=ResumeDetailRead)
async def get_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeDetailRead:
    return await resume_service.get_resume_with_sections(
        db, resume_id=resume_id, user_id=current_user.id
    )


@router.get("/{resume_id}/analysis", response_model=ResumeAnalysisRead)
async def get_resume_analysis(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeAnalysisRead:
    return await resume_service.get_latest_analysis_for_user(
        db, resume_id=resume_id, user_id=current_user.id
    )


@router.get("/{resume_id}/matches", response_model=list[JobMatchWithJobRead])
async def list_resume_matches(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JobMatchWithJobRead]:
    """Powers the job-comparison dashboard: every job this resume has been
    matched against, newest first, with just enough job context (title/
    company) to render a comparison table."""
    matches = await job_service.list_matches_for_resume(
        db, resume_id=resume_id, user_id=current_user.id
    )
    return [
        JobMatchWithJobRead(
            **JobMatchRead.model_validate(match).model_dump(),
            job_title=match.job.title,
            job_company=match.job.company,
        )
        for match in matches
    ]
