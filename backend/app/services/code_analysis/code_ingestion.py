"""
Codebase Ingestion for RAG — Phase 6.

Chunking and vector indexing of repository source code into the pgvector RAG pipeline.
"""
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embeddings import embed_batch
from app.rag.chunking import chunk_text
from app.models.rag import RAGDocument, RAGChunk
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CodeIngestionService:
    """Ingests source code files into pgvector RAG pipeline."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_code_file(
        self,
        user_id: uuid.UUID,
        repo_id: uuid.UUID,
        repo_name: str,
        file_path: str,
        content: str,
    ) -> int:
        """Chunk, embed, and store a code file in rag_documents and rag_chunks."""
        if not content.strip():
            return 0

        settings = get_settings()

        # Create virtual document header to give RAG context on file location
        doc_header = f"File: {file_path} in repository {repo_name}\n\n"
        chunks = chunk_text(
            doc_header + content,
            size=settings.CODE_INGEST_CHUNK_SIZE,
            overlap=settings.CODE_INGEST_CHUNK_OVERLAP,
        )

        if not chunks:
            return 0

        embeddings = await embed_batch(chunks)

        # 1. Create RAGDocument
        doc = RAGDocument(
            user_id=user_id,
            source_type="codebase",
            source_id=repo_id,
            title=f"{repo_name}: {file_path}",
            metadata_json={"repo_id": str(repo_id), "repo_name": repo_name, "file_path": file_path},
        )
        self.db.add(doc)
        await self.db.flush()

        # 2. Create RAGChunks
        db_chunks = []
        for i, (text, emb) in enumerate(zip(chunks, embeddings)):
            metadata = {
                "repo_id": str(repo_id),
                "repo_name": repo_name,
                "file_path": file_path,
            }
            chunk_obj = RAGChunk(
                user_id=user_id,
                document_id=doc.id,
                chunk_index=i,
                content=text,
                embedding=emb,
                metadata_json=metadata,
            )
            db_chunks.append(chunk_obj)

        self.db.add_all(db_chunks)
        await self.db.flush()
        return len(db_chunks)
