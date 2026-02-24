"""LLM client with streaming and JSON support (OpenAI-compatible API)."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

import httpx

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

# Regex to strip markdown code fences: ```json ... ``` or ``` ... ```
_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n(.*?)\n```\s*$", re.DOTALL)


class LLMClient:
    """Async wrapper around an OpenAI-compatible chat completions API."""

    def __init__(self, api_key: str, model: str = "minimax/minimax-m2.5", base_url: str = DEFAULT_BASE_URL, timeout: float = 60.0) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.completions_url = f"{self.base_url}/chat/completions"
        self.http = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    # ------------------------------------------------------------------
    # Non-streaming chat
    # ------------------------------------------------------------------

    async def chat(
        self, messages: list[dict], temperature: float = 0.7, max_tokens: int | None = None
    ) -> str:
        """Non-streaming chat. Returns the content string."""
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        response = await self.http.post(self.completions_url, json=body)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Streaming chat
    # ------------------------------------------------------------------

    async def chat_stream(
        self, messages: list[dict], temperature: float = 0.7, max_tokens: int | None = None
    ) -> AsyncIterator[str]:
        """Streaming chat. Yields text chunks as they arrive via SSE."""
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        async with self.http.stream(
            "POST",
            self.completions_url,
            json=body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload.strip() == "[DONE]":
                    break
                chunk_data = json.loads(payload)
                delta = chunk_data["choices"][0]["delta"]
                content = delta.get("content")
                if content:
                    yield content

    # ------------------------------------------------------------------
    # JSON chat
    # ------------------------------------------------------------------

    async def chat_json(
        self, messages: list[dict], temperature: float = 0.3
    ) -> dict | list:
        """Chat expecting a JSON response.

        Strips markdown code fences if present, then parses JSON.
        """
        raw = await self.chat(messages, temperature=temperature)
        text = raw.strip()

        # Strip markdown fences if present
        fence_match = _FENCE_RE.match(text)
        if fence_match:
            text = fence_match.group(1)

        return json.loads(text)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.http.aclose()
