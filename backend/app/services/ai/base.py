"""
AI provider abstraction (spec section 15: "Create an AI service abstraction
so another model/provider can be added later").

Every place in the app that needs an LLM call goes through this interface,
never through a provider SDK directly. Swapping providers means writing one
new class here, not touching resume_service, the interview agent, etc.

We intentionally keep the interface to a single method that returns
already-parsed JSON: nearly every use in this app (resume review, skill
gap, interview questions, ...) wants structured output, and centralizing
the "ask for JSON, strip code fences, parse, validate" logic here means
each caller doesn't reinvent it slightly differently.
"""
from abc import ABC, abstractmethod
from typing import Any


class AIProviderError(Exception):
    """Raised when the provider can't produce a usable structured response —
    missing API key, network/timeout failure, or the model didn't return
    parseable JSON. Callers are expected to catch this and fall back to a
    deterministic heuristic rather than fail the whole request."""


class AIProvider(ABC):
    @abstractmethod
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """Send a prompt, return the model's response parsed as a JSON object.

        Raises AIProviderError if the provider is unavailable or the
        response isn't valid JSON — callers must handle this rather than
        assume it always succeeds.
        """
        raise NotImplementedError

    async def generate_text(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 1200) -> str:
        """Text response helper for RAG answers; providers may override it."""
        data = await self.generate_json(system_prompt, user_prompt, max_tokens=max_tokens)
        return str(data.get("answer", ""))
