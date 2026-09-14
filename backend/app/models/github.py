"""
GitHub Integration models — Phase 6.

Four tables:
- GitHubConnection: encrypted OAuth token per user
- GitHubRepository: user-selected repos to analyse
- CodeAnalysisReport: one per analysis run (summary stats)
- CodeFinding: individual detected issues (potential, with evidence)

Design decisions:
- Token is stored AES-GCM encrypted — never returned to the client.
- All findings are labelled "potential" — the system never claims certainty.
- Each finding includes file_path + line range + verbatim code_evidence so
  developers can quickly locate the flagged code.
- Severity and category are string enums (not PG native enums) so SQLite
  test mode works without dialect-specific DDL.
"""
import enum
import uuid

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RepoStatus(str, enum.Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    INDEXED = "indexed"
    FAILED = "failed"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(str, enum.Enum):
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    STYLE = "style"


class GitHubConnection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Stores an encrypted GitHub access token for one user.

    encrypted_token: AES-GCM ciphertext (hex-encoded) — key stored separately.
    token_scope:     The OAuth scopes granted (e.g. "repo,read:user").
    github_login:    Username shown in the UI — never used for auth decisions.
    """
    __tablename__ = "github_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # one connection per user
        index=True,
    )
    github_login: Mapped[str] = mapped_column(String(255), nullable=False)
    github_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AES-GCM: "<hex-nonce>:<hex-ciphertext>"
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_scope: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    repositories: Mapped[list["GitHubRepository"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class GitHubRepository(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A user-selected GitHub repository that has been synced into CareerForge.

    status lifecycle: idle → syncing → indexed | failed
    """
    __tablename__ = "github_repositories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("github_connections.id", ondelete="CASCADE"), nullable=False
    )

    # GitHub metadata
    github_repo_id: Mapped[int] = mapped_column(Integer, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)   # e.g. "octocat/Hello-World"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    primary_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    languages_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    html_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Sync state
    status: Mapped[RepoStatus] = mapped_column(
        Enum(RepoStatus, native_enum=False, length=20),
        nullable=False,
        default=RepoStatus.IDLE,
    )
    files_indexed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    connection: Mapped["GitHubConnection"] = relationship(back_populates="repositories")
    reports: Mapped[list["CodeAnalysisReport"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class CodeAnalysisReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One analysis run over a GitHubRepository.

    summary_json contains counts by severity and category, top affected files, etc.
    """
    __tablename__ = "code_analysis_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("github_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Whether LLM-assisted review was included
    llm_review_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_files_analysed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # {"by_severity": {...}, "by_category": {...}, "top_files": [...]}
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    repository: Mapped["GitHubRepository"] = relationship(back_populates="reports")
    findings: Mapped[list["CodeFinding"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class CodeFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single detected potential issue in a source file.

    IMPORTANT: Every finding is labelled a *potential* issue — not a confirmed
    vulnerability.  The `description` always starts with "Potential issue:".

    code_evidence: The verbatim source lines that triggered this finding.
                   Stored so the UI can render a code block without re-fetching
                   the file from GitHub.
    """
    __tablename__ = "code_findings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("code_analysis_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("github_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification
    pattern_id: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[FindingCategory] = mapped_column(
        Enum(FindingCategory, native_enum=False, length=20), nullable=False, index=True
    )
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, native_enum=False, length=20), nullable=False, index=True
    )

    # Location
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Content
    # Always prefixed "Potential issue: " — enforced in report_builder
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Verbatim source excerpt — enables evidence display without GitHub re-fetch
    code_evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Optional: LLM-generated explanation (null for static-only findings)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped["CodeAnalysisReport"] = relationship(back_populates="findings")
