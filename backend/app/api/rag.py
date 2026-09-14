"""
RAG API routes — Phase 5.

All routes require authentication (get_current_user dependency).
Every service call passes current_user.id so the pipeline can enforce
user-level authorization on every DB query.

Route summary:
  POST   /rag/reindex                              — rebuild vector index for current user
  POST   /rag/conversations                        — create a new conversation
  GET    /rag/conversations                        — list all conversations for current user
  DELETE /rag/conversations/{id}                   — delete a conversation + its messages
  GET    /rag/conversations/{id}/messages          — fetch message history
  POST   /rag/conversations/{id}/messages          — ask a question (non-streaming)
  POST   /rag/conversations/{id}/messages/stream   — ask a question (SSE streaming)
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.rag.pipeline import rag_pipeline
from app.schemas.rag import (
    ChatAnswer,
    ChatAsk,
    ConversationCreate,
    ConversationList,
    ConversationRead,
    MessageRead,
    ReindexStatus,
)

router = APIRouter(prefix="/rag", tags=["rag"])


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

@router.post("/reindex", response_model=ReindexStatus, summary="Rebuild vector index")
async def reindex(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReindexStatus:
    """
    Delete and rebuild the entire vector index for the authenticated user.

    Sources indexed:
    - All resumes with extracted text (raw_text IS NOT NULL)
    - All resume sections for those resumes
    - All job descriptions

    Only this user's data is ever touched — other users' indexes are
    completely isolated at the database level (WHERE user_id = ?).
    """
    count = await rag_pipeline.reindex_user(db, current_user.id)
    return ReindexStatus(chunks_indexed=count)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@router.post(
    "/conversations",
    response_model=ConversationRead,
    status_code=201,
    summary="Create conversation",
)
async def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    conv = await rag_pipeline.create_conversation(db, current_user.id, payload.title)
    return ConversationRead.model_validate(conv)


@router.get(
    "/conversations",
    response_model=ConversationList,
    summary="List all conversations",
)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationList:
    convs = await rag_pipeline.list_conversations(db, current_user.id)
    items = [ConversationRead.model_validate(c) for c in convs]
    return ConversationList(conversations=items, total=len(items))


@router.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    summary="Delete conversation",
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await rag_pipeline.delete_conversation(db, current_user.id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageRead],
    summary="Get conversation history",
)
async def get_history(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageRead]:
    messages = await rag_pipeline.get_messages(db, current_user.id, conversation_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [MessageRead.model_validate(m) for m in messages]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatAnswer,
    summary="Send a message (non-streaming)",
)
async def chat(
    conversation_id: uuid.UUID,
    payload: ChatAsk,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatAnswer:
    """
    Full RAG pipeline (non-streaming):
    embed question → pgvector ANN search → inject history → LLM → return answer + citations.
    """
    try:
        answer, citations = await rag_pipeline.ask(
            db,
            current_user.id,
            conversation_id,
            payload.question,
            payload.source_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ChatAnswer(conversation_id=conversation_id, answer=answer, citations=citations)


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    summary="Send a message (SSE streaming)",
)
async def chat_stream(
    conversation_id: uuid.UUID,
    payload: ChatAsk,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Streaming RAG pipeline using Server-Sent Events (SSE).

    Event sequence:
      data: {"type":"citations","data":[...]}   ← emitted first
      data: {"type":"token","data":"Hello"}      ← one per LLM token
      data: {"type":"token","data":" world"}
      ...
      data: {"type":"done","data":""}            ← end of stream

    The frontend consumes this with EventSource or fetch+ReadableStream.
    Citations are emitted before the first token so the UI can render the
    citations panel while the answer is still streaming.
    """
    async def event_generator():
        # Verify conversation ownership before starting the stream
        messages = await rag_pipeline.get_messages(db, current_user.id, conversation_id)
        if messages is None:
            yield f"data: {json.dumps({'type': 'error', 'data': 'Conversation not found'})}\n\n"
            return

        async for event in rag_pipeline.ask_stream(
            db,
            current_user.id,
            conversation_id,
            payload.question,
            payload.source_types,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering in production
        },
    )
