"""
RAG Pipeline — Phase 5 production implementation.

Architecture overview
---------------------

                  ┌──────────────┐
  Document ──────►│  clean_text  │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │   chunking   │  (word-boundary or section-aware)
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │  embed_batch │  (Ollama nomic-embed-text or local hash)
                  └──────┬───────┘
                         │
                  ┌──────▼───────────────────────────────────┐
                  │  PostgreSQL / pgvector                   │
                  │  rag_documents  +  rag_chunks            │
                  │  (embedding_vector vector(384), IVFFlat) │
                  └──────┬───────────────────────────────────┘
                         │  ANN similarity search  (cosine <=>)
                         │  + user_id filter (authorization)
                         │  + optional source_type filter
                  ┌──────▼───────┐
                  │  top-K chunks│
                  └──────┬───────┘
                         │
                  ┌──────▼────────────────┐
                  │  context construction │  [Source N: title]\ncontent
                  └──────┬────────────────┘
                         │
                  ┌──────▼──────────────────────────────┐
                  │  LLM  (Anthropic / Ollama)          │
                  │  system: "answer from context only" │
                  │  user:   history + context + Q      │
                  └──────┬──────────────────────────────┘
                         │
                  ┌──────▼────────────────────────────┐
                  │  Answer + citations saved to DB   │
                  └───────────────────────────────────┘

User-level authorization
------------------------
Every DB query in this module carries `WHERE user_id = :current_user_id`.
This is enforced in the service layer (here), not at the HTTP layer, so it
cannot be bypassed by a crafted request.  Even if a caller passes a
conversation_id that belongs to another user, `_get_conversation` returns
None, and `ask()` raises ValueError → 404.

pgvector search
---------------
Native SQL:
    SET LOCAL ivfflat.probes = :probes;
    SELECT rc.*, rd.*
    FROM   rag_chunks rc
    JOIN   rag_documents rd ON rd.id = rc.document_id
    WHERE  rc.user_id = :user_id
      AND  (:source_types IS NULL OR rd.source_type = ANY(:source_types))
    ORDER  BY rc.embedding_vector <=> CAST(:query_vec AS vector)
    LIMIT  :k;

The CAST is required because asyncpg sends the vector as a plain string and
PostgreSQL needs to know to interpret it as vector type.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import AsyncIterator

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.job import Job
from app.models.rag import ChatMessage, Conversation, RAGChunk, RAGDocument
from app.models.resume import Resume, ResumeSection
from app.rag.chunking import chunk_by_section, chunk_text
from app.rag.embeddings import embed, embed_batch
from app.schemas.rag import CitationRead


@dataclass
class RetrievedChunk:
    """A single ranked result from the vector search."""
    chunk: RAGChunk
    document: RAGDocument
    score: float  # 1 = identical, 0 = orthogonal (cosine similarity)


class RAGPipeline:
    """
    Central abstraction for the full RAG lifecycle.

    One instance is created at startup and reused across requests.
    All methods accept `db` as an argument (not stored as instance state)
    so the pipeline is compatible with FastAPI's per-request session pattern.
    """

    # -----------------------------------------------------------------------
    # Ingestion
    # -----------------------------------------------------------------------

    async def ingest(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        title: str,
        text_content: str,
        metadata: dict | None = None,
        *,
        use_section_chunking: bool = False,
    ) -> int:
        """
        Ingest a single document into the vector store.

        Steps: clean → chunk → embed (batch) → upsert to rag_documents + rag_chunks.

        Returns:
            Number of chunks created.
        """
        settings = get_settings()
        metadata = metadata or {}

        # Choose chunking strategy
        if use_section_chunking:
            chunks = chunk_by_section(
                text_content, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP
            )
        else:
            chunks = chunk_text(
                text_content, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP
            )

        if not chunks:
            return 0

        # Create parent document row
        document = RAGDocument(
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            title=title,
            metadata_json=metadata,
        )
        db.add(document)
        await db.flush()

        # Batch-embed all chunks in one Ollama round-trip
        vectors = await embed_batch(chunks)

        for index, (content, vector) in enumerate(zip(chunks, vectors)):
            chunk = RAGChunk(
                user_id=user_id,
                document_id=document.id,
                chunk_index=index,
                content=content,
                metadata_json=metadata,
                embedding=vector,  # JSON column (used as fallback / tests)
            )
            db.add(chunk)
            await db.flush()

            # Populate the native pgvector column for production ANN search.
            # We detect PostgreSQL by checking the dialect name at runtime.
            if self._is_postgres(db):
                vec_str = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
                await db.execute(
                    text(
                        "UPDATE rag_chunks "
                        "SET embedding_vector = CAST(:vec AS vector) "
                        "WHERE id = :id"
                    ),
                    {"vec": vec_str, "id": chunk.id},
                )

        return len(chunks)

    async def reindex_user(self, db: AsyncSession, user_id: uuid.UUID) -> int:
        """
        Delete all existing chunks/documents for *user_id* and rebuild from
        the current state of their resumes, resume sections, and jobs.

        Authorized sources only — nothing from other users is ever touched.
        """
        # Purge existing index for this user only
        await db.execute(delete(RAGChunk).where(RAGChunk.user_id == user_id))
        await db.execute(delete(RAGDocument).where(RAGDocument.user_id == user_id))

        settings = get_settings()
        total = 0

        # --- Resumes (full raw text) ---
        resumes = (
            await db.execute(
                select(Resume).where(
                    Resume.user_id == user_id,
                    Resume.raw_text.is_not(None),
                )
            )
        ).scalars().all()

        for resume in resumes:
            total += await self.ingest(
                db,
                user_id,
                source_type="resume",
                source_id=resume.id,
                title=resume.original_filename,
                text_content=resume.raw_text or "",
                metadata={"file_type": resume.file_type},
            )

            # --- Resume Sections (section-aware chunking) ---
            sections = (
                await db.execute(
                    select(ResumeSection).where(ResumeSection.resume_id == resume.id)
                )
            ).scalars().all()

            for section in sections:
                total += await self.ingest(
                    db,
                    user_id,
                    source_type="resume_section",
                    source_id=section.id,
                    title=f"{resume.original_filename} — {section.section_type.value.title()}",
                    text_content=section.content,
                    metadata={
                        "resume_id": str(resume.id),
                        "section": section.section_type.value,
                        "file_type": resume.file_type,
                    },
                    use_section_chunking=True,
                )

        # --- Jobs ---
        jobs = (
            await db.execute(select(Job).where(Job.user_id == user_id))
        ).scalars().all()

        for job in jobs:
            title = f"{job.title or 'Job'}" + (f" @ {job.company}" if job.company else "")
            total += await self.ingest(
                db,
                user_id,
                source_type="job",
                source_id=job.id,
                title=title,
                text_content=job.raw_description,
                metadata={"status": job.status.value},
            )

        await db.commit()
        return total

    # -----------------------------------------------------------------------
    # Retrieval (similarity search)
    # -----------------------------------------------------------------------

    async def search(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        question: str,
        *,
        source_types: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Embed *question* and return the top-K most similar authorized chunks.

        Authorization: user_id filter is always applied; results from other
        users are physically impossible to return.

        On PostgreSQL: uses native pgvector ANN search (IVFFlat index).
        On SQLite (tests): falls back to Python cosine over the JSON embedding column.
        """
        settings = get_settings()
        k = top_k or settings.RAG_TOP_K
        query_vec = await embed(question)

        if self._is_postgres(db):
            return await self._pgvector_search(db, user_id, query_vec, source_types, k)
        else:
            return await self._fallback_cosine(db, user_id, query_vec, source_types, k)

    async def _pgvector_search(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query_vec: list[float],
        source_types: list[str] | None,
        k: int,
    ) -> list[RetrievedChunk]:
        """
        Native pgvector similarity search with IVFFlat index.

        How it works:
        1. SET ivfflat.probes tells pgvector how many Voronoi cells to scan.
           More probes = better recall at the cost of latency.
        2. The <=> operator computes cosine distance (1 - cosine_similarity).
           ORDER BY ASC means the closest vector (most similar) comes first.
        3. user_id filter is enforced at SQL level — the database physically
           can't return rows from another user.
        4. Optional source_type filter allows the user to restrict search to
           only their resume, only job descriptions, etc.
        """
        settings = get_settings()
        probes = settings.RAG_IVFFLAT_PROBES
        vec_str = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"

        # Set search quality for this transaction
        await db.execute(text(f"SET LOCAL ivfflat.probes = {probes}"))

        if source_types:
            sql = text(
                """
                SELECT rc.id        AS chunk_id,
                       rc.content,
                       rc.metadata_json,
                       rc.chunk_index,
                       rc.embedding,
                       rd.id        AS doc_id,
                       rd.source_type,
                       rd.source_id,
                       rd.title,
                       rd.metadata_json AS doc_meta,
                       1 - (rc.embedding_vector <=> CAST(:vec AS vector)) AS score
                FROM   rag_chunks rc
                JOIN   rag_documents rd ON rd.id = rc.document_id
                WHERE  rc.user_id = :uid
                  AND  rc.embedding_vector IS NOT NULL
                  AND  rd.source_type = ANY(:stypes)
                ORDER  BY rc.embedding_vector <=> CAST(:vec AS vector)
                LIMIT  :k
                """
            )
            rows = (
                await db.execute(sql, {"vec": vec_str, "uid": user_id, "stypes": source_types, "k": k})
            ).mappings().all()
        else:
            sql = text(
                """
                SELECT rc.id        AS chunk_id,
                       rc.content,
                       rc.metadata_json,
                       rc.chunk_index,
                       rc.embedding,
                       rd.id        AS doc_id,
                       rd.source_type,
                       rd.source_id,
                       rd.title,
                       rd.metadata_json AS doc_meta,
                       1 - (rc.embedding_vector <=> CAST(:vec AS vector)) AS score
                FROM   rag_chunks rc
                JOIN   rag_documents rd ON rd.id = rc.document_id
                WHERE  rc.user_id = :uid
                  AND  rc.embedding_vector IS NOT NULL
                ORDER  BY rc.embedding_vector <=> CAST(:vec AS vector)
                LIMIT  :k
                """
            )
            rows = (
                await db.execute(sql, {"vec": vec_str, "uid": user_id, "k": k})
            ).mappings().all()

        results = []
        for row in rows:
            # Re-hydrate lightweight dataclass objects from the raw mapping
            chunk = RAGChunk(
                id=row["chunk_id"],
                user_id=user_id,
                document_id=row["doc_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                metadata_json=row["metadata_json"] or {},
                embedding=row["embedding"] or [],
            )
            document = RAGDocument(
                id=row["doc_id"],
                user_id=user_id,
                source_type=row["source_type"],
                source_id=row["source_id"],
                title=row["title"],
                metadata_json=row["doc_meta"] or {},
            )
            results.append(RetrievedChunk(chunk=chunk, document=document, score=float(row["score"])))

        return results

    async def _fallback_cosine(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query_vec: list[float],
        source_types: list[str] | None,
        k: int,
    ) -> list[RetrievedChunk]:
        """Python cosine similarity — SQLite / offline tests only."""
        import math

        stmt = (
            select(RAGChunk, RAGDocument)
            .join(RAGDocument, RAGChunk.document_id == RAGDocument.id)
            .where(RAGChunk.user_id == user_id, RAGDocument.user_id == user_id)
        )
        if source_types:
            stmt = stmt.where(RAGDocument.source_type.in_(source_types))

        rows = (await db.execute(stmt)).all()

        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            mag = (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1.0
            return dot / mag

        ranked = sorted(
            ((cosine(chunk.embedding or [], query_vec), chunk, doc) for chunk, doc in rows),
            key=lambda t: t[0],
            reverse=True,
        )[:k]

        return [RetrievedChunk(chunk=c, document=d, score=s) for s, c, d in ranked]

    # -----------------------------------------------------------------------
    # Context construction
    # -----------------------------------------------------------------------

    def build_context(self, results: list[RetrievedChunk]) -> str:
        """
        Format retrieved chunks into a numbered source block for the LLM.

        Output format:
            [Source 1: Resume — Work Experience]
            ... chunk text ...

            [Source 2: Job: Senior Engineer @ Acme]
            ... chunk text ...

        The LLM system prompt instructs the model to cite as [Source N],
        so the numbering here must match the citation list we return.
        """
        blocks = []
        for i, result in enumerate(results, start=1):
            header = f"[Source {i}: {result.document.title}]"
            blocks.append(f"{header}\n{result.chunk.content}")
        return "\n\n".join(blocks)

    def build_citations(self, results: list[RetrievedChunk]) -> list[CitationRead]:
        """Build the citation list returned to the frontend."""
        return [
            CitationRead(
                document_id=r.document.id,
                source_type=r.document.source_type,
                source_id=r.document.source_id,
                title=r.document.title,
                excerpt=r.chunk.content[:320],
                score=round(r.score, 4),
            )
            for r in results
        ]

    # -----------------------------------------------------------------------
    # Conversation management
    # -----------------------------------------------------------------------

    async def create_conversation(
        self, db: AsyncSession, user_id: uuid.UUID, title: str
    ) -> Conversation:
        conv = Conversation(user_id=user_id, title=title)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv

    async def list_conversations(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[Conversation]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars())

    async def delete_conversation(
        self, db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> bool:
        conv = await self._get_conversation(db, user_id, conversation_id)
        if conv is None:
            return False
        await db.delete(conv)
        await db.commit()
        return True

    async def get_messages(
        self, db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> list[ChatMessage] | None:
        if not await self._get_conversation(db, user_id, conversation_id):
            return None
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        )
        return list(result.scalars())

    # -----------------------------------------------------------------------
    # Answer generation (non-streaming)
    # -----------------------------------------------------------------------

    async def ask(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        question: str,
        source_types: list[str] | None = None,
    ) -> tuple[str, list[CitationRead]]:
        """
        Full RAG pipeline: search → context → history → LLM → persist.

        Returns (answer_text, citations).
        Raises ValueError if the conversation doesn't belong to this user.
        """
        conversation = await self._get_conversation(db, user_id, conversation_id)
        if conversation is None:
            raise ValueError("Conversation not found or not owned by user")

        # 1. Retrieve relevant chunks (pgvector ANN)
        results = await self.search(db, user_id, question, source_types=source_types)

        # 2. Build context block
        context = self.build_context(results)
        citations = self.build_citations(results)

        # 3. Fetch conversation history (last N turns)
        history_text = await self._build_history(db, conversation_id)

        # 4. Call LLM
        answer = await self._call_llm(question, context, history_text)

        # 5. Persist both messages
        db.add(
            ChatMessage(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=question,
                citations=[],
            )
        )
        db.add(
            ChatMessage(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=answer,
                citations=[c.model_dump(mode="json") for c in citations],
            )
        )
        await db.commit()
        return answer, citations

    async def ask_stream(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        question: str,
        source_types: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        """
        Streaming RAG pipeline — yields SSE-compatible dicts.

        Yields:
            {"type": "citations", "data": [...]} — sent first so the UI can
                render the citations panel before the answer starts streaming.
            {"type": "token", "data": "..."} — one or more partial answer tokens.
            {"type": "done", "data": ""} — signals end of stream.

        Full answer is accumulated and persisted to DB after streaming completes.
        """
        conversation = await self._get_conversation(db, user_id, conversation_id)
        if conversation is None:
            yield {"type": "error", "data": "Conversation not found"}
            return

        results = await self.search(db, user_id, question, source_types=source_types)
        context = self.build_context(results)
        citations = self.build_citations(results)
        history_text = await self._build_history(db, conversation_id)

        # Send citations first — UI renders panel while answer streams
        yield {"type": "citations", "data": [c.model_dump(mode="json") for c in citations]}

        # Persist user message before streaming
        db.add(
            ChatMessage(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=question,
                citations=[],
            )
        )
        await db.flush()

        # Stream tokens from LLM
        full_answer = ""
        async for token in self._stream_llm(question, context, history_text):
            full_answer += token
            yield {"type": "token", "data": token}

        # Persist assistant message
        db.add(
            ChatMessage(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=full_answer,
                citations=[c.model_dump(mode="json") for c in citations],
            )
        )
        await db.commit()
        yield {"type": "done", "data": ""}

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _get_conversation(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Conversation | None:
        """Always filters by user_id — cannot return another user's conversation."""
        return (
            await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,  # authorization guard
                )
            )
        ).scalar_one_or_none()

    async def _build_history(self, db: AsyncSession, conversation_id: uuid.UUID) -> str:
        """
        Fetch the last RAG_HISTORY_TURNS message pairs and format them as a
        conversation transcript to inject into the LLM prompt.

        Why inject history?
        Without history, every question is answered in isolation — the user
        can't say "tell me more about that" or "compare it to the previous job".
        With history, the LLM has context about what was already discussed.
        """
        settings = get_settings()
        # Each "turn" = 1 user + 1 assistant message → fetch 2× turns
        limit = settings.RAG_HISTORY_TURNS * 2
        rows = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()

        # Reverse to chronological order
        rows = list(reversed(rows))

        if not rows:
            return ""

        lines = []
        for msg in rows:
            prefix = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)

    async def _call_llm(self, question: str, context: str, history: str) -> str:
        """
        Build the full prompt and call the configured LLM provider.

        Prompt structure:
        ┌─────────────────────────────────────────────────────────────────┐
        │ SYSTEM:                                                         │
        │   You are CareerForge AI, a career intelligence assistant.     │
        │   If career documents are available, use them and cite sources. │
        │   Otherwise, answer from general career knowledge.             │
        │                                                                 │
        │ USER:                                                           │
        │   [Conversation History]                                        │
        │   <previous turns>                                              │
        │                                                                 │
        │   [Context from your career documents]  ← if available         │
        │   [Source 1: …]  chunk …                                       │
        │   [Source 2: …]  chunk …                                       │
        │                                                                 │
        │   Question: <current question>                                  │
        └─────────────────────────────────────────────────────────────────┘
        """
        from app.services.ai import get_ai_provider

        if context:
            system = (
                "You are CareerForge AI, a career intelligence assistant. "
                "Use the provided context from the user's career documents to answer. "
                "When citing information, reference it as [Source N] matching the numbered "
                "sources in the context. Be concise, specific, and actionable. "
                "If the context doesn't cover the question, supplement with general career advice "
                "and clearly indicate which parts come from documents vs. general knowledge."
            )
        else:
            system = (
                "You are CareerForge AI, a career intelligence assistant. "
                "The user has not yet uploaded any career documents (resume, job descriptions, etc.). "
                "Answer their question using your general knowledge of careers, resumes, job searching, "
                "and professional development. Be helpful, concise, and actionable. "
                "If the question is specifically about their personal documents, politely suggest they "
                "upload a resume or job description first using the Resume or Jobs section."
            )

        user_parts: list[str] = []
        if history:
            user_parts.append(f"[Conversation History]\n{history}")
        if context:
            user_parts.append(f"[Context from your career documents]\n{context}")
        user_parts.append(f"Question: {question}")

        user_prompt = "\n\n".join(user_parts)

        provider = get_ai_provider()
        if provider:
            try:
                return await provider.generate_text(system, user_prompt, max_tokens=1500)
            except Exception:
                pass  # fall through to deterministic answer

        # Deterministic fallback (no provider / API error)
        if not context:
            return (
                "Hi! I'm CareerForge AI. You haven't uploaded any career documents yet. "
                "To get personalized answers, please upload your resume in the Resume section "
                "or add a job description in the Jobs section. "
                "Once indexed, I can analyze your experience, match you to jobs, and more!"
            )
        return "Based on your indexed career documents:\n\n" + context

    async def _stream_llm(
        self, question: str, context: str, history: str
    ) -> AsyncIterator[str]:
        """
        Yield tokens from the LLM stream, or fall back to a non-streaming call.
        """
        from app.services.ai import get_ai_provider
        from app.core.config import get_settings

        if context:
            system = (
                "You are CareerForge AI, a career intelligence assistant. "
                "Use the provided context from the user's career documents to answer. "
                "Cite sources as [Source N]. Be concise and actionable. "
                "If the context doesn't fully cover the question, supplement with general career advice "
                "and clearly indicate which parts come from documents vs. general knowledge."
            )
        else:
            system = (
                "You are CareerForge AI, a career intelligence assistant. "
                "The user has not yet uploaded any career documents. "
                "Answer using your general knowledge of careers, resumes, job searching, "
                "and professional development. Be helpful, concise, and actionable. "
                "If the question is specifically about their personal documents, politely suggest "
                "they upload a resume or job description first."
            )

        user_parts: list[str] = []
        if history:
            user_parts.append(f"[Conversation History]\n{history}")
        if context:
            user_parts.append(f"[Context from your career documents]\n{context}")
        user_parts.append(f"Question: {question}")
        user_prompt = "\n\n".join(user_parts)

        provider = get_ai_provider()
        settings = get_settings()

        # Try Ollama streaming first
        if settings.LLM_PROVIDER == "ollama" and provider is not None:
            from app.services.ai.ollama_provider import OllamaProvider
            if isinstance(provider, OllamaProvider):
                try:
                    async for token in provider.stream_text(system, user_prompt):
                        yield token
                    return
                except Exception as e:
                    # Fall back gracefully if Ollama model is missing or fails
                    import logging
                    import traceback
                    print(f"OLLAMA STREAM ERROR: {e}")
                    traceback.print_exc()
                    logging.getLogger(__name__).error(f"Ollama streaming failed: {e}", exc_info=True)
                    pass

        # Non-streaming fallback — emit entire answer as one "token"
        if provider:
            try:
                answer = await provider.generate_text(system, user_prompt, max_tokens=1500)
                yield answer
                return
            except Exception as e:
                import logging
                import traceback
                print(f"OLLAMA GENERATE ERROR: {e}")
                traceback.print_exc()
                logging.getLogger(__name__).error(f"Generate text fallback failed: {e}", exc_info=True)
                pass

        # Final fallback (no LLM available)
        if context:
            yield "Based on your career documents, here is what I found:\n\n"
            yield context
        else:
            yield (
                "Hi! I'm CareerForge AI. You haven't uploaded any career documents yet. "
                "To get personalized answers, please upload your resume in the Resume section "
                "or add a job description in the Jobs section. "
                "Once indexed, I can analyze your experience, match you to jobs, and much more!"
            )

    @staticmethod
    def _is_postgres(db: AsyncSession) -> bool:
        """Detect whether the session is backed by PostgreSQL."""
        try:
            return db.bind.dialect.name == "postgresql"  # type: ignore[union-attr]
        except AttributeError:
            return False


# Module-level singleton — instantiated once at import time, shared across requests.
rag_pipeline = RAGPipeline()
