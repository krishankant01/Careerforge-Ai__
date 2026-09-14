import asyncio
from app.services.ai.ollama_provider import OllamaProvider
from app.core.config import get_settings

async def main():
    settings = get_settings()
    provider = OllamaProvider(base_url="http://127.0.0.1:11434", model=settings.LLM_MODEL)
    print(f"Testing stream_text with model {settings.LLM_MODEL}...")
    try:
        async for token in provider.stream_text("System prompt", "User prompt"):
            print(token, end="", flush=True)
        print("\nSuccess.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
