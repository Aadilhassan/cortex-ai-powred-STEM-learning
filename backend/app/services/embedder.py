"""Embeddings via OpenRouter API (qwen/qwen3-embedding-8b)."""

from __future__ import annotations

import httpx


class Embedder:
    """Generates embeddings using OpenRouter's embedding API."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.model = model
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector."""
        resp = await self.client.post(
            "/embeddings",
            json={"model": self.model, "input": text},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings into vectors."""
        resp = await self.client.post(
            "/embeddings",
            json={"model": self.model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # Sort by index to maintain order
        data.sort(key=lambda x: x["index"])
        return [d["embedding"] for d in data]

    async def close(self):
        await self.client.aclose()
