"""
Centralized application configuration.

Why pydantic-settings instead of `os.environ.get(...)` scattered everywhere?
- Values are validated once, at startup (fail fast if DATABASE_URL is missing,
  instead of crashing mysteriously three requests later).
- Autocomplete + type checking in your editor.
- One place to see every environment variable the app depends on.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "CareerForge AI"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://careerforge:careerforge@localhost:5432/careerforge"

    # --- Auth (used starting Phase 2, declared now so .env is stable) ---
    JWT_SECRET: str = "change-me-in-env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # --- AI provider (used starting Phase 3) ---
    LLM_API_KEY: str | None = None
    LLM_PROVIDER: str = "anthropic"  # abstraction target; see app/services/ai
    LLM_MODEL: str = "claude-sonnet-4-6"
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_AUTO_PULL: bool = True  # pull embedding + LLM models on startup if absent
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSIONS: int = 384  # must match the model; update when switching models
    RAG_CHUNK_SIZE: int = 900
    RAG_CHUNK_OVERLAP: int = 150
    RAG_TOP_K: int = 6
    RAG_HISTORY_TURNS: int = 6     # number of past conversation turns injected into context
    RAG_IVFFLAT_PROBES: int = 10   # pgvector IVFFlat search quality (higher = slower but better recall)

    # --- Resume uploads (Phase 3) ---
    UPLOAD_DIR: str = "uploads/resumes"
    MAX_RESUME_FILE_SIZE_MB: int = 5
    ALLOWED_RESUME_EXTENSIONS: list[str] = [".pdf", ".docx"]

    # --- GitHub (Phase 6) ---
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:5173/github/callback"
    # AES-GCM key for encrypting stored GitHub tokens; defaults to JWT_SECRET
    # override in prod to a 32-byte random hex string: `openssl rand -hex 32`
    GITHUB_TOKEN_ENCRYPTION_KEY: str | None = None

    # --- Code Analysis (Phase 6) ---
    CODE_ANALYSIS_MAX_FILE_KB: int = 100          # skip files larger than this
    CODE_ANALYSIS_MAX_REPO_FILES: int = 500        # hard cap per repo sync
    CODE_INGEST_CHUNK_SIZE: int = 600              # code chunk size (chars)
    CODE_INGEST_CHUNK_OVERLAP: int = 100           # overlap between code chunks
    CODE_ANALYSIS_LLM_REVIEW_DEFAULT: bool = False # opt-in deep LLM review

    # --- Web search (Phase 7 research agent) ---
    SEARCH_API_KEY: str | None = None

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance. `lru_cache` means the .env file is parsed once,
    not on every request — settings are effectively a singleton.
    """
    return Settings()
