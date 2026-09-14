"""
Resume Intelligence models (spec sections 6 & 26).

Three tables, deliberately kept separate:

- Resume: one row per uploaded file. Tracks the upload/processing lifecycle
  (status) independently of whether analysis has ever succeeded.
- ResumeSection: the parsed sections (Skills, Experience, ...) for a resume.
  Split out from Resume.raw_text so a future feature (e.g. per-section
  embeddings in the Phase 4 RAG pipeline) has something to attach to
  without re-parsing.
- ResumeAnalysis: one row per analysis *run*. A resume can be re-analyzed
  (e.g. after the scoring rubric changes) without losing the history of
  previous runs — the API always serves the latest one.
"""
import enum
import uuid

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ResumeStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SectionType(str, enum.Enum):
    SUMMARY = "summary"
    SKILLS = "skills"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    OTHER = "other"


class Resume(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resumes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The name the user uploaded, kept only for display — never used to
    # build a filesystem path (see resume_service.save_uploaded_file).
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "pdf" | "docx"
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[ResumeStatus] = mapped_column(
        Enum(ResumeStatus, native_enum=False, length=20),
        nullable=False,
        default=ResumeStatus.PENDING,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    sections: Mapped[list["ResumeSection"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["ResumeAnalysis"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Resume id={self.id} user_id={self.user_id} status={self.status}>"


class ResumeSection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_sections"

    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_type: Mapped[SectionType] = mapped_column(
        Enum(SectionType, native_enum=False, length=20), nullable=False
    )
    # Where this section fell in the original document — lets the UI
    # render sections in the order the candidate wrote them.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    resume: Mapped["Resume"] = relationship(back_populates="sections")


class ResumeAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resume_analyses"

    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    ats_score: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_score: Mapped[int] = mapped_column(Integer, nullable=False)
    experience_score: Mapped[int] = mapped_column(Integer, nullable=False)
    project_score: Mapped[int] = mapped_column(Integer, nullable=False)
    skill_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # Every field below is JSON because its shape is inherently a list/dict
    # (evidence lists, per-score explanations) — see app/schemas/resume.py
    # for the shape callers can actually rely on.
    score_explanations: Mapped[dict] = mapped_column(JSON, nullable=False)
    detected_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ats_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # "deterministic" (no LLM involved/available) or "ai_assisted" — surfaced
    # to the client so the UI can be honest about how experience/project
    # scores and the narrative feedback were produced.
    analysis_mode: Mapped[str] = mapped_column(String(20), nullable=False)

    resume: Mapped["Resume"] = relationship(back_populates="analyses")

    def __repr__(self) -> str:
        return f"<ResumeAnalysis id={self.id} resume_id={self.resume_id} overall={self.overall_score}>"
