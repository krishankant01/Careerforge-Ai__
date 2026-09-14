"""
Import every model here. Alembic's env.py imports `Base.metadata` from this
package to autogenerate migrations — a model that isn't imported here is
invisible to `alembic revision --autogenerate`.
"""
from app.models.base import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.resume import Resume, ResumeAnalysis, ResumeSection  # noqa: F401
from app.models.job import Job, JobMatch  # noqa: F401
from app.models.rag import ChatMessage, Conversation, RAGChunk, RAGDocument  # noqa: F401
from app.models.github import (  # noqa: F401
    GitHubConnection, GitHubRepository, CodeAnalysisReport, CodeFinding,
)
