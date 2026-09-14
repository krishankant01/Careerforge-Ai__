"""
Application entrypoint.

Run with: uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.github import router as github_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.rag import router as rag_router
from app.api.resumes import router as resumes_router
from app.api.agent_api import router as agent_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered Career & Code Intelligence platform.",
    version="0.1.0",
    debug=settings.DEBUG,
)

# CORS: only the frontend origin(s) listed in settings may call this API
# with credentials. Wildcard "*" is never used now that auth headers are
# involved (Phase 2).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.rate_limit import limiter

# Consistent { success, error: { code, message } } JSON on every failure
# (spec section 30) — registered before routers so it covers all of them.
register_exception_handlers(app)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(resumes_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(github_router, prefix="/api")
app.include_router(agent_router, prefix="/api")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("%s starting up (environment=%s)", settings.APP_NAME, settings.ENVIRONMENT)

    # Phase 5: auto-pull Ollama models so the first /reindex or /chat
    # request doesn't fail with "model not found".
    if settings.OLLAMA_AUTO_PULL and settings.EMBEDDING_PROVIDER == "ollama":
        from app.rag.embeddings import ensure_model_pulled
        from app.services.ai.ollama_provider import OllamaProvider

        logger.info("Pulling Ollama embedding model: %s", settings.EMBEDDING_MODEL)
        await ensure_model_pulled(settings.EMBEDDING_MODEL)

        if settings.LLM_PROVIDER == "ollama":
            logger.info("Pulling Ollama LLM model: %s", settings.LLM_MODEL)
            try:
                await OllamaProvider.pull_model(settings.OLLAMA_BASE_URL, settings.LLM_MODEL)
                logger.info("Ollama LLM model ready: %s", settings.LLM_MODEL)
            except Exception as exc:
                # Non-fatal: the app still works with Anthropic or the
                # deterministic fallback if Ollama is unavailable.
                logger.warning("Could not pull Ollama LLM model %s: %s", settings.LLM_MODEL, exc)


@app.get("/")
async def root() -> dict:
    return {"message": "CareerForge AI API", "docs": "/docs"}
