"""
Ollama AI provider — Phase 5 upgrade.

New in Phase 5:
- stream_text(): async generator that yields tokens from Ollama's streaming API.
  This enables the SSE /messages/stream endpoint to deliver real-time responses.
- pull_model(): pulls a model from the Ollama registry if not already local.
  Called at application startup when OLLAMA_AUTO_PULL=True.
"""
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.services.ai.base import AIProvider, AIProviderError


class OllamaProvider(AIProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    # -----------------------------------------------------------------------
    # Core AIProvider interface
    # -----------------------------------------------------------------------

    async def generate_json(
        self, system_prompt: str, user_prompt: str, *, max_tokens: int = 2000
    ) -> dict[str, Any]:
        import re
        text = await self.generate_text(system_prompt, user_prompt, max_tokens=max_tokens)
        text = text.strip()

        # Strategy 1: strip markdown fences (```json ... ```)
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("{"):
                    text = candidate
                    break

        # Strategy 2: extract the first {...} block (handles preamble text)
        if not text.startswith("{"):
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                text = match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIProviderError(f"Ollama did not return valid JSON: {text[:200]}") from exc


    async def generate_text(
        self, system_prompt: str, user_prompt: str, *, max_tokens: int = 1200
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "system": system_prompt,
                        "prompt": user_prompt,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    },
                )
                response.raise_for_status()
                return str(response.json()["response"]).strip()
        except Exception as exc:
            raise AIProviderError(f"Ollama generate_text failed: {exc}") from exc

    # -----------------------------------------------------------------------
    # Streaming (Phase 5)
    # -----------------------------------------------------------------------

    async def stream_text(
        self, system_prompt: str, user_prompt: str, *, max_tokens: int = 1500
    ) -> AsyncIterator[str]:
        """
        Yield response tokens as they arrive from Ollama's streaming API.

        Ollama streams newline-delimited JSON objects:
            {"model":"llama3.1","response":"Hello","done":false}
            {"model":"llama3.1","response":" world","done":false}
            {"model":"llama3.1","response":"","done":true}

        We yield the "response" field of each non-done line.
        """
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "system": system_prompt,
                        "prompt": user_prompt,
                        "stream": True,
                        "options": {"num_predict": max_tokens},
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = obj.get("response", "")
                        if token:
                            yield token
                        if obj.get("done", False):
                            break
        except Exception as exc:
            raise AIProviderError(f"Ollama stream_text failed: {exc}") from exc

    # -----------------------------------------------------------------------
    # Model management (Phase 5)
    # -----------------------------------------------------------------------

    @classmethod
    async def pull_model(cls, base_url: str, model: str) -> None:
        """
        Pull *model* from the Ollama registry if it is not already local.

        Ollama's /api/pull returns newline-delimited JSON with status updates.
        We consume them silently — callers just need to know it completed.
        Errors are raised so the startup handler can log them.
        """
        base_url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=600) as client:  # models can be large
            async with client.stream(
                "POST",
                f"{base_url}/api/pull",
                json={"model": model, "stream": True},
            ) as response:
                response.raise_for_status()
                async for _ in response.aiter_lines():
                    pass  # consume the stream — we only care about completion
