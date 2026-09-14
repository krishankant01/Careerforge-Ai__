# RAG Pipeline

The Retrieval-Augmented Generation (RAG) system powers the CareerForge AI chat and context injection.

## 1. Ingestion (`app.rag.pipeline`)
When a user uploads a resume or pastes a job description, it is ingested automatically in a background task:
1. **Cleaning**: HTML tags and extra whitespace are removed.
2. **Chunking**: Text is split into chunks of ~900 characters with 150 characters of overlap. For resumes, "section-aware chunking" keeps entire experiences (e.g., a specific job role) in the same chunk.
3. **Embedding**: Chunks are embedded into 384-dimensional vectors using `nomic-embed-text` via Ollama.
4. **Storage**: Vectors are inserted into PostgreSQL `rag_chunks`.

## 2. Retrieval
When a user asks a question:
1. The question is embedded.
2. An exact cosine distance similarity search is executed using `pgvector`'s `<=>` operator against the `rag_chunks` table.
3. The query strictly filters `WHERE user_id = :uid` to guarantee data privacy.
4. The top-K results are returned and formatted into a source citation block.

## 3. Generation
The LLM is prompted with:
1. System Prompt
2. Conversation History
3. Retrieved Context (cited as `[Source N]`)
4. The User's Question

This ensures the AI grounds its answers strictly in the user's provided career history.
