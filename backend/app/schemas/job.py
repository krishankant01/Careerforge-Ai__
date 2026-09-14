"""Pydantic schemas for the Job Analyzer + Matching API (spec section 27)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus


class JobCreateRequest(BaseModel):
    raw_description: str = Field(min_length=50, max_length=20000)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: JobStatus
    failure_reason: str | None = None
    title: str | None = None
    company: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    responsibilities: list[str] | None = None
    experience_requirement: str | None = None
    education_requirement: str | None = None
    parse_mode: str | None = None
    created_at: datetime
    updated_at: datetime


class JobMatchRequest(BaseModel):
    resume_id: uuid.UUID


class SkillMatchRead(BaseModel):
    model_config = ConfigDict(extra="allow")

    skill: str
    requirement_level: str
    match_type: str
    matched_resume_skill: str | None
    confidence: float
    reasoning: str


class JobMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID
    compatibility_score: int
    required_coverage_score: int
    preferred_coverage_score: int
    skill_matches: list[SkillMatchRead]
    score_explanation: dict
    semantic_mode: str
    created_at: datetime


class JobMatchWithJobRead(JobMatchRead):
    """Used by the comparison dashboard — includes enough job context
    (title/company) to render a table without a second round-trip per row."""

    job_title: str | None = None
    job_company: str | None = None
