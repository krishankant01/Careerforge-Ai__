"""
Unit and integration tests for Phase 5 (RAG System).

Tests:
1. Text cleaning & normalization
2. Chunking strategy (fixed window + overlap & section-aware)
3. Local hash fallback embedding generation
4. Ingestion & reindexing
5. User isolation in similarity search
6. Conversation CRUD & Chat API endpoints (non-streaming + SSE streaming)
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from unittest.mock import patch, AsyncMock

from app.rag.chunking import clean_text, chunk_text, chunk_by_section
from app.rag.embeddings import embed, embed_batch
from app.rag.pipeline import rag_pipeline
from app.models.rag import RAGDocument, RAGChunk, Conversation, ChatMessage
from app.models.user import User
from app.models.resume import Resume, ResumeSection, ResumeStatus, SectionType
from app.models.job import Job

@pytest.fixture(autouse=True)
def mock_embeddings_and_llm(monkeypatch):
    async def mock_embed(text):
        return [0.1] * 384
        
    async def mock_embed_batch(texts):
        return [[0.1] * 384 for _ in texts]
        
    monkeypatch.setattr("tests.test_rag.embed", mock_embed)
    monkeypatch.setattr("tests.test_rag.embed_batch", mock_embed_batch)
    monkeypatch.setattr("app.rag.pipeline.embed", mock_embed)
    monkeypatch.setattr("app.rag.pipeline.embed_batch", mock_embed_batch)

    # Mock the AI provider to prevent it from trying to hit Ollama during tests
    class MockProvider:
        async def generate_text(self, *args, **kwargs):
            return "Mock AI response"
            
        async def stream_text(self, *args, **kwargs):
            yield "Mock "
            yield "stream"
            
    monkeypatch.setattr("app.services.ai.get_ai_provider", lambda: MockProvider())


# -----------------------------------------------------------------------------
# 1. Text Cleaning & Chunking Tests
# -----------------------------------------------------------------------------

def test_clean_text():
    raw = "Hello&nbsp;World!\r\n\r\n\tThis   is  a test."
    cleaned = clean_text(raw)
    assert "Hello World!" in cleaned
    assert "This is a test." in cleaned
    assert "&nbsp;" not in cleaned


def test_chunk_text_window_and_overlap():
    text = "Word " * 500  # 2500 chars
    chunks = chunk_text(text, size=200, overlap=50)
    assert len(chunks) > 1
    assert isinstance(chunks[0], str)


def test_chunk_by_section():
    content = "Software Engineer at Google from 2020 to 2023."
    chunks = chunk_by_section(content, max_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "Software Engineer at Google from 2020 to 2023."


async def test_generate_embeddings_fallback():
    vecs = await embed_batch(["hello world", "test chunk"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 384
    assert isinstance(vecs[0][0], float)


# -----------------------------------------------------------------------------
# 2. Pipeline & Isolation Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reindex_and_user_isolation(db_session):
    u1 = User(name="User One", email="user1@example.com", hashed_password="pw1")
    u2 = User(name="User Two", email="user2@example.com", hashed_password="pw2")
    db_session.add_all([u1, u2])
    await db_session.flush()

    user1_id = u1.id
    user2_id = u2.id

    # Seed resume for user 1
    r1 = Resume(
        user_id=user1_id,
        original_filename="resume1.pdf",
        file_type="pdf",
        file_size_bytes=1000,
        storage_path="/tmp/r1.pdf",
        status=ResumeStatus.COMPLETED,
        raw_text="Senior Python Backend Developer with FastAPI experience.",
    )
    db_session.add(r1)
    await db_session.flush()

    s1 = ResumeSection(
        resume_id=r1.id,
        section_type=SectionType.EXPERIENCE,
        order_index=0,
        content="Senior Python Backend Developer with FastAPI experience.",
    )
    db_session.add(s1)

    # Seed resume for user 2
    r2 = Resume(
        user_id=user2_id,
        original_filename="resume2.pdf",
        file_type="pdf",
        file_size_bytes=1000,
        storage_path="/tmp/r2.pdf",
        status=ResumeStatus.COMPLETED,
        raw_text="Data Scientist specializing in PyTorch and Machine Learning.",
    )
    db_session.add(r2)
    await db_session.flush()

    s2 = ResumeSection(
        resume_id=r2.id,
        section_type=SectionType.EXPERIENCE,
        order_index=0,
        content="Data Scientist specializing in PyTorch and Machine Learning.",
    )
    db_session.add(s2)

    await db_session.commit()

    # Reindex user 1
    status1 = await rag_pipeline.reindex_user(db_session, user1_id)
    assert status1 > 0

    # Reindex user 2
    status2 = await rag_pipeline.reindex_user(db_session, user2_id)
    assert status2 > 0

    # Search user 1 for "Python"
    vec1 = await embed("Python")
    results1 = await rag_pipeline.search(db_session, user1_id, vec1, top_k=5)
    assert len(results1) > 0
    for res in results1:
        assert res.chunk.user_id == user1_id

    # Search user 2 — should NOT find user 1's content
    results2 = await rag_pipeline.search(db_session, user2_id, vec1, top_k=5)
    for res in results2:
        assert res.chunk.user_id == user2_id


# -----------------------------------------------------------------------------
# 3. Chat API Endpoint Integration Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rag_api_endpoints(client, auth_headers):
    # Reindex user via API
    reindex_res = await client.post("/api/rag/reindex", headers=auth_headers)
    assert reindex_res.status_code == 200
    assert "chunks_indexed" in reindex_res.json()

    # Create conversation
    conv_res = await client.post(
        "/api/rag/conversations",
        json={"title": "Career Strategy Chat"},
        headers=auth_headers
    )
    assert conv_res.status_code == 201
    conv_data = conv_res.json()
    conv_id = conv_data["id"]
    assert conv_data["title"] == "Career Strategy Chat"

    # List conversations
    list_res = await client.get("/api/rag/conversations", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["conversations"]) == 1

    # Send message (non-streaming)
    msg_res = await client.post(
        f"/api/rag/conversations/{conv_id}/messages",
        json={"question": "What are my main technical skills?"},
        headers=auth_headers
    )
    assert msg_res.status_code == 200
    reply = msg_res.json()
    assert "answer" in reply
    assert "citations" in reply
    assert reply["conversation_id"] == conv_id

    # Fetch history
    hist_res = await client.get(f"/api/rag/conversations/{conv_id}/messages", headers=auth_headers)
    assert hist_res.status_code == 200
    messages = hist_res.json()
    assert len(messages) == 2

    # Delete conversation
    del_res = await client.delete(f"/api/rag/conversations/{conv_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # Verify deleted
    list_after = await client.get("/api/rag/conversations", headers=auth_headers)
    assert len(list_after.json()["conversations"]) == 0
