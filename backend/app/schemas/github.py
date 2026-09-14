"""
Pydantic schemas for GitHub Integration & Code Intelligence — Phase 6.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.github import FindingCategory, FindingSeverity, RepoStatus


class GitHubConnectPATRequest(BaseModel):
    personal_access_token: str = Field(..., min_length=1, description="GitHub Personal Access Token")


class GitHubConnectOAuthRequest(BaseModel):
    code: str = Field(..., min_length=1, description="OAuth authorization code from GitHub callback")


class GitHubConnectionResponse(BaseModel):
    id: uuid.UUID
    github_login: str
    github_user_id: int
    avatar_url: str | None = None
    token_scope: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class GitHubRepositoryResponse(BaseModel):
    id: uuid.UUID
    github_repo_id: int
    full_name: str
    name: str
    description: str | None = None
    default_branch: str
    primary_language: str | None = None
    languages_json: dict = {}
    stars: int = 0
    is_private: bool = False
    html_url: str
    status: RepoStatus
    files_indexed: int = 0
    error_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CodeFindingResponse(BaseModel):
    id: uuid.UUID
    pattern_id: str
    category: FindingCategory
    severity: FindingSeverity
    file_path: str
    line_start: int
    line_end: int
    description: str
    suggestion: str
    code_evidence: str
    llm_explanation: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CodeAnalysisReportResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    llm_review_included: bool
    total_files_analysed: int
    total_findings: int
    summary_json: dict
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyzeRepoRequest(BaseModel):
    include_llm_review: bool = False


class CodebaseQAQuery(BaseModel):
    query: str = Field(..., min_length=1)
    repository_id: uuid.UUID | None = None  # optional filter to specific repo


class CodebaseQAResponse(BaseModel):
    answer: str
    citations: list[dict]
