"""
RAG service — Phase 5.

This module is now a thin delegation layer over app.rag.pipeline.RAGPipeline.
All business logic lives in the pipeline; this module exists so that any
existing code that imported from app.services.rag_service continues to work.

New code should import from app.rag.pipeline directly.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import ChatMessage, Conversation
from app.rag.pipeline import rag_pipeline
from app.schemas.rag import CitationRead


async def reindex_user_sources(db: AsyncSession, user_id: uuid.UUID) -> int:
    return await rag_pipeline.reindex_user(db, user_id)


async def create_conversation(
    db: AsyncSession, user_id: uuid.UUID, title: str
) -> Conversation:
    return await rag_pipeline.create_conversation(db, user_id, title)


async def get_conversation(
    db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation | None:
    from sqlalchemy import select
    from app.models.rag import Conversation
    return (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def ask(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    question: str,
    source_types: list[str] | None = None,
) -> tuple[str, list[CitationRead]]:
    return await rag_pipeline.ask(db, user_id, conversation_id, question, source_types)


async def messages(
    db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[ChatMessage] | None:
    return await rag_pipeline.get_messages(db, user_id, conversation_id)
