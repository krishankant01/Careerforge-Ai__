"""
RAG data models — Phase 5 upgrade.

Changes from Phase 4:
- RAGChunk: embedding column kept as JSON for test/SQLite compat; the native
  pgvector column (embedding_vector) is added via migration 0004 and managed
  by the pipeline.
- ChatMessage: added user_id for direct authorization checks without a JOIN.
  This means we can confirm "this message belongs to this user" in one query.
- Conversation: added metadata_json for future features (pinned, archived, etc.).
"""
import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RAGDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One row per indexed source (resume, resume section, or job description).

    source_type: "resume" | "resume_section" | "job"
    source_id:   FK to the originating table row (e.g. resumes.id)
    user_id:     Always set — every retrieval query filters on this column.
    """
    __tablename__ = "rag_documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    chunks: Mapped[list["RAGChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class RAGChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One chunk of a RAGDocument.

    embedding:        JSON list of floats — used as fallback for SQLite tests
                      and for backwards compat with old rows.
    embedding_vector: pgvector native column (vector(384)) — added by migration
                      0004 via ALTER TABLE, not visible to SQLAlchemy ORM
                      directly, managed via raw SQL in the pipeline.
    """
    __tablename__ = "rag_chunks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # JSON fallback — same data as embedding_vector but portable across DBs
    embedding: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    document: Mapped["RAGDocument"] = relationship(back_populates="chunks")


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A named chat thread belonging to one user.

    metadata_json: reserved for future features — e.g. pinned, archived, tags.
    """
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Career chat")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ChatMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single user or assistant message within a Conversation.

    user_id: denormalised from Conversation for fast per-user auth checks
             without a JOIN. See migration 0005.
    role:    "user" | "assistant"
    citations: JSON list of CitationRead dicts attached to assistant messages.
    """
    __tablename__ = "chat_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
