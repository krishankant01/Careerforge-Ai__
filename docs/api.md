# API Documentation

The backend is built with FastAPI. Interactive documentation (Swagger UI) is available at `/docs` when the server is running.

## Authentication
All protected routes require a JWT token in the `Authorization` header:
`Authorization: Bearer <token>`

## Key Endpoints

### `/api/auth`
- `POST /register`: Create a new account.
- `POST /login`: Authenticate and receive a JWT.

### `/api/resumes`
- `POST /upload`: Upload a PDF/DOCX. Automatically triggers a background task for RAG ingestion and LLM parsing.
- `GET /`: List all uploaded resumes.

### `/api/jobs`
- `POST /`: Add a target job description. Triggers a background match analysis against the user's active resume.

### `/api/rag`
- `POST /reindex`: Manually rebuild the vector index for the current user.
- `POST /conversations/{id}/messages`: Query the RAG system.

### `/api/agents`
- `POST /chat`: Interact with the multi-agent system. The payload takes a `message` and `conversation_id`.

## Rate Limiting
Public endpoints are protected via SlowAPI (e.g., `/api/auth/login` is limited to 10 requests per minute per IP).
