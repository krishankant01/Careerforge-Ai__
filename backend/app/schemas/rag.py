"""
RAG Pydantic schemas — Phase 5.

All schemas that cross the HTTP boundary live here.
Internal-only types (RetrievedChunk etc.) live in app/rag/pipeline.py.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------

class CitationRead(BaseModel):
    """A single cited source returned alongside an LLM answer."""
    document_id: uuid.UUID
    source_type: str        # "resume" | "resume_section" | "job"
    source_id: uuid.UUID
    title: str
    excerpt: str            # First 320 chars of the chunk
    score: float            # Cosine similarity [0, 1]


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class ConversationCreate(BaseModel):
    title: str = Field(default="Career chat", min_length=1, max_length=255)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    created_at: datetime


class ConversationList(BaseModel):
    """Wrapper for list endpoints — makes pagination easy to add later."""
    conversations: list[ConversationRead]
    total: int


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatAsk(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    source_types: list[str] | None = Field(
        default=None,
        description="Filter retrieval to specific source types. "
                    "Allowed values: 'resume', 'resume_section', 'job'. "
                    "Omit to search all authorized sources.",
    )


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: str
    content: str
    citations: list[Any] = []
    created_at: datetime


class ChatAnswer(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    citations: list[CitationRead]


# ---------------------------------------------------------------------------
# Reindex
# ---------------------------------------------------------------------------

class ReindexStatus(BaseModel):
    chunks_indexed: int
    source_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="chunks_indexed split by source_type",
    )
    message: str = "Reindex complete"


# ---------------------------------------------------------------------------
# Streaming (SSE)
# ---------------------------------------------------------------------------

class StreamEvent(BaseModel):
    """
    A single server-sent event payload.

    type:
        "citations" — data is list[CitationRead] dicts; sent first.
        "token"     — data is a string token from the LLM stream.
        "done"      — data is ""; stream is complete.
        "error"     — data is an error message string.
    """
    type: str
    data: Any
