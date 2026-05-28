from __future__ import annotations
import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str | None = None):
        self._base = (base_url or settings.ollama_url).rstrip("/")
        self._http = httpx.AsyncClient(timeout=120.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def ping(self) -> bool:
        try:
            r = await self._http.get(f"{self._base}/api/tags")
            return r.status_code == 200
        except Exception:
            return False

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or settings.embed_model
        r = await self._http.post(
            f"{self._base}/api/embeddings",
            json={"model": model, "prompt": text},
        )
        r.raise_for_status()
        return r.json()["embedding"]

    async def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> dict:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                **kwargs,
            },
        }
        r = await self._http.post(f"{self._base}/api/chat", json=payload)
        r.raise_for_status()
        return r.json()

    async def list_models(self) -> list[str]:
        try:
            r = await self._http.get(f"{self._base}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception as exc:
            logger.error("Failed to list Ollama models: %s", exc)
            return []

    async def pull_model(self, model: str) -> None:
        logger.info("Pulling Ollama model: %s", model)
        async with self._http.stream(
            "POST", f"{self._base}/api/pull", json={"name": model}
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    logger.debug("pull: %s", line)


_default_client: OllamaClient | None = None


def get_ollama() -> OllamaClient:
    global _default_client
    if _default_client is None:
        _default_client = OllamaClient()
    return _default_client
