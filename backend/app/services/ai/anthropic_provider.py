"""
Anthropic implementation of AIProvider. This is the only file that imports
the `anthropic` SDK — if we ever add a second provider (OpenAI, local model,
etc.) it lives next to this one and app/services/ai/__init__.py picks between
them, with zero changes anywhere else in the app.
"""
import json
import re
from typing import Any

from app.core.logging import get_logger
from app.services.ai.base import AIProvider, AIProviderError

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        # Imported lazily so the rest of the app can run (and be tested)
        # without the anthropic package installed, if a deployment never
        # configures this provider.
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - any SDK/network failure becomes AIProviderError
            logger.warning("Anthropic call failed: %s", exc)
            raise AIProviderError(f"AI provider request failed: {exc}") from exc

        text_blocks = [block.text for block in response.content if block.type == "text"]
        raw_text = "\n".join(text_blocks).strip()
        cleaned = _JSON_FENCE_RE.sub("", raw_text).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("Anthropic response was not valid JSON: %s", raw_text[:500])
            raise AIProviderError("AI provider did not return valid JSON") from exc
