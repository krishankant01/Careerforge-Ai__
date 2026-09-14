"""
Factory for the configured AI provider.

Callers should import get_ai_provider from here (never construct a
provider class directly) so that (a) provider selection stays driven by
settings.LLM_PROVIDER, and (b) tests can monkeypatch this single function
to inject a fake provider instead of needing a real API key.
"""
from app.core.config import get_settings
from app.services.ai.base import AIProvider, AIProviderError

__all__ = ["AIProvider", "AIProviderError", "get_ai_provider"]


def get_ai_provider() -> AIProvider | None:
    """Returns None (not an error) when no provider is configured — callers
    treat "no provider" the same as "provider call failed" and use their
    deterministic fallback, so a missing API key degrades a feature instead
    of breaking it."""
    settings = get_settings()
    if settings.LLM_PROVIDER == "ollama":
        from app.services.ai.ollama_provider import OllamaProvider
        return OllamaProvider(base_url=settings.OLLAMA_BASE_URL, model=settings.LLM_MODEL)

    if not settings.LLM_API_KEY:
        return None

    if settings.LLM_PROVIDER == "anthropic":
        from app.services.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=settings.LLM_API_KEY, model=settings.LLM_MODEL)

    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")
