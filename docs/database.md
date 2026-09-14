# Database Architecture

The application uses PostgreSQL with the `pgvector` extension.

## Migrations
We use Alembic for asynchronous schema migrations.
To run migrations:
```bash
alembic upgrade head
```

## Schema Overview

### Users Table (`users`)
- Stores authentication data (email, hashed password) and profile metadata.

### Resumes Table (`resumes`)
- Tracks uploaded documents, parsing status, and original file metadata.
- **Child Tables**: `resume_sections` (splits the resume into parseable chunks like Experience, Education).

### Jobs Table (`jobs`)
- Stores target job descriptions for the user.

### Job Matches Table (`job_matches`)
- Stores the calculated compatibility score between a `resume_id` and `job_id`, including skill gaps.

### Code Intelligence Tables
- `github_repos`: Connected repositories.
- `github_files`: Synced source code files from repositories.
- `code_reviews`: LLM-generated code reviews for specific files.

### RAG Tables
- `rag_documents`: Virtual documents grouping chunks.
- `rag_chunks`: The actual vector embeddings.
  - Features an `embedding_vector` column of type `VECTOR(384)`.
  - Indexed using an IVFFlat index for fast nearest-neighbor lookups.

## Data Security
All sensitive queries enforce a `WHERE user_id = :uid` strict isolation boundary at the SQLAlchemy level.
