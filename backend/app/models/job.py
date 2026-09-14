"""
Job Description Analyzer + Job Matching models (spec sections 7, 8, 26).

Job: one row per pasted job description, with the same
pending/processing/completed/failed lifecycle as Resume (Phase 3) — parsing
can involve an AI call, so it runs as a background task rather than
blocking the create request.

JobMatch: one row per (resume, job) comparison *run*. Kept as its own table
(not merged into Job or Resume) because the same resume can be matched
against many jobs, and the same job can be matched against many resumes —
it's a many-to-many join with a rich payload, not a property of either side.
"""
import enum
import uuid

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=20), nullable=False, default=JobStatus.PENDING
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Parsed fields — nullable until status == COMPLETED.
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    preferred_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    responsibilities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    experience_requirement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    education_requirement: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # "deterministic" (regex/heuristic section+skill parsing only) or
    # "ai_assisted" (LLM extracted title/skills/responsibilities) — same
    # honesty convention as Resume.analysis_mode in Phase 3.
    parse_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)

    matches: Mapped[list["JobMatch"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title!r} status={self.status}>"


class JobMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_matches"

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    compatibility_score: Mapped[int] = mapped_column(Integer, nullable=False)
    required_coverage_score: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_coverage_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # One entry per job skill (required + preferred combined):
    # { skill, requirement_level: "required"|"preferred",
    #   match_type: "exact"|"inferred"|"semantic"|"missing",
    #   matched_resume_skill: str | None, evidence: str | None,
    #   confidence: float, reasoning: str }
    skill_matches: Mapped[list] = mapped_column(JSON, nullable=False)
    score_explanation: Mapped[dict] = mapped_column(JSON, nullable=False)

    # "deterministic" or "ai_assisted" — whether the semantic-match layer
    # used the curated related-skills map or an actual LLM judgment call.
    semantic_mode: Mapped[str] = mapped_column(String(20), nullable=False)

    job: Mapped["Job"] = relationship(back_populates="matches")

    def __repr__(self) -> str:
        return f"<JobMatch job_id={self.job_id} resume_id={self.resume_id} score={self.compatibility_score}>"
