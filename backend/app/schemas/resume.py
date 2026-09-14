"""Pydantic schemas for the Resume Intelligence API (spec sections 6, 27)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.resume import ResumeStatus, SectionType


class ResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_type: str
    file_size_bytes: int
    status: ResumeStatus
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ResumeSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_type: SectionType
    order_index: int
    content: str


class ScoreExplanation(BaseModel):
    """Every sub-score's explanation is a free-form dict because the checks
    behind ATS/Technical/Skill scores differ in shape from the AI-grounded
    reasoning behind Experience/Project scores — see
    app/services/resume/scoring.py and ai_review.py for what each contains."""

    model_config = ConfigDict(extra="allow")


class ResumeAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_id: uuid.UUID
    overall_score: int
    ats_score: int
    technical_score: int
    experience_score: int
    project_score: int
    skill_score: int
    score_explanations: dict
    detected_skills: list
    missing_keywords: list
    ats_issues: list
    strengths: list
    weaknesses: list
    analysis_mode: str
    created_at: datetime


class ResumeDetailRead(ResumeRead):
    sections: list[ResumeSectionRead] = []
