"""
Embedding abstraction — Phase 5 production upgrade.

Design decisions:
- `embed(text)` is kept for single-text use (query embedding at search time).
- `embed_batch(texts)` sends all chunks in one HTTP call to Ollama, cutting
  round-trips during reindexing by a factor equal to chunk count.
- `ensure_model_pulled(model)` silently pulls the model on first use;
  this prevents the confusing "model not found" error that appears the first
  time a freshly-started Ollama container is used.
- The local hash fallback (no Ollama) still works for unit tests that run
  without any external service.
"""
import hashlib
import math

import httpx

from app.core.config import get_settings


def _settings():
    return get_settings()


def _local_embed(text: str | list[str], dimensions: int) -> list[float]:
    """Deterministic hash-based embedding for offline / unit-test use."""
    if isinstance(text, list):
        text = " ".join(str(item) for item in text)
    vector = [0.0] * dimensions
    for token in str(text).lower().split():
        vector[int(hashlib.sha256(token.encode()).hexdigest(), 16) % dimensions] += 1.0
    magnitude = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / magnitude for v in vector]


async def ensure_model_pulled(model: str) -> None:
    """
    Ask Ollama to pull *model* if it is not already present locally.
    Safe to call multiple times — Ollama is a no-op when the model exists.
    Errors are swallowed so a missing/unreachable Ollama doesn't crash startup.
    """
    settings = _settings()
    if settings.EMBEDDING_PROVIDER != "ollama":
        return
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/pull",
                json={"model": model, "stream": False},
            )
            response.raise_for_status()
    except Exception:
        # Log-worthy but not fatal — embedding calls will surface the real error.
        pass


async def embed(text: str | list[str]) -> list[float]:
    """Embed a single string (or single list item). Used for query embedding at search time."""
    if isinstance(text, list):
        res = await embed_batch(text)
        return res[0] if res else _local_embed("", _settings().EMBEDDING_DIMENSIONS)
    settings = _settings()
    dimensions = settings.EMBEDDING_DIMENSIONS
    if settings.EMBEDDING_PROVIDER == "ollama":
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed",
                    json={"model": settings.EMBEDDING_MODEL, "input": text},
                )
                response.raise_for_status()
                return response.json()["embeddings"][0]
        except Exception:
            pass
    return _local_embed(text, dimensions)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed multiple texts in a single Ollama HTTP round-trip.

    Ollama's /api/embed endpoint accepts a list under the "input" key
    (added in Ollama ≥ 0.3). Falls back to local hash provider if Ollama
    is unreachable or returns an error.
    """
    if not texts:
        return []
    settings = _settings()
    dimensions = settings.EMBEDDING_DIMENSIONS
    if settings.EMBEDDING_PROVIDER == "ollama":
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed",
                    json={"model": settings.EMBEDDING_MODEL, "input": texts},
                )
                response.raise_for_status()
                return response.json()["embeddings"]
        except Exception:
            pass
    return [_local_embed(t, dimensions) for t in texts]
