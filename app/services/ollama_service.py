import json
import logging
from typing import AsyncGenerator
import httpx

from core.settings import settings

logger = logging.getLogger(__name__)


class OllamaService:
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.default_model = "gemma4:31b-cloud"
        # self.default_model = settings.ollama_model
        self.default_temperature = settings.ollama_temperature

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams chat completion tokens asynchronously from Ollama /api/chat.
        Yields raw delta token strings as they arrive.
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else self.default_temperature,
            },
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            try:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        logger.error("Ollama streaming error %d: %s", response.status_code, error_body.decode())
                        yield f"[Error: Ollama service returned {response.status_code}]"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            message = data.get("message", {})
                            delta = message.get("content", "")
                            if delta:
                                yield delta
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

            except httpx.ConnectError as e:
                logger.error("Failed to connect to Ollama at %s: %s", url, str(e))
                yield f"[Error: Unable to connect to Ollama at {self.base_url}. Ensure the Ollama container is running.]"
            except Exception as e:
                logger.error("Exception during Ollama streaming: %s", str(e), exc_info=True)
                yield f"[Error during generation: {str(e)}]"

    def generate(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        Synchronous chat generation (used by Celery workers or blocking tasks).
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.default_temperature,
            },
        }

        try:
            with httpx.Client(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                response = client.post(url, json=payload)
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama returned {response.status_code}: {response.text}")
                data = response.json()
                return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error("Ollama sync generation error: %s", str(e), exc_info=True)
            raise e


ollama_service = OllamaService()
