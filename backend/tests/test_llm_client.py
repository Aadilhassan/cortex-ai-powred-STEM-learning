"""Tests for the Z.ai LLM client."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.llm_client import LLMClient


# ---------------------------------------------------------------------------
# Helper mocks for async iteration (SSE streaming)
# ---------------------------------------------------------------------------

class AsyncIteratorMock:
    """Mock that implements async iteration over a list of items."""

    def __init__(self, items):
        self.items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration


class AsyncContextMock:
    """Mock that implements async context manager wrapping a value."""

    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_returns_content():
    """chat() returns the content string from a non-streaming response."""
    client = LLMClient(api_key="test-key")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}]
    }

    client.http.post = AsyncMock(return_value=mock_response)

    result = await client.chat([{"role": "user", "content": "Hi"}])
    assert result == "Hello!"

    # Verify the request was made correctly
    client.http.post.assert_called_once()
    call_kwargs = client.http.post.call_args
    assert call_kwargs[0][0] == "https://api.z.ai/api/paas/v4/chat/completions"
    body = call_kwargs[1]["json"]
    assert body["model"] == "glm-4.7"
    assert body["messages"] == [{"role": "user", "content": "Hi"}]
    assert body["temperature"] == 0.7
    assert body["stream"] is False

    await client.close()


@pytest.mark.asyncio
async def test_chat_stream_yields_chunks():
    """chat_stream() yields text chunks parsed from SSE lines."""
    client = LLMClient(api_key="test-key")

    # Simulate SSE lines as they come from the server
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        "",  # blank line between events
        "data: [DONE]",
    ]

    mock_stream_response = MagicMock()
    mock_stream_response.aiter_lines = lambda: AsyncIteratorMock(sse_lines)

    client.http.stream = MagicMock(
        return_value=AsyncContextMock(mock_stream_response)
    )

    chunks = []
    async for chunk in client.chat_stream([{"role": "user", "content": "Hi"}]):
        chunks.append(chunk)

    assert chunks == ["Hello", " world"]

    await client.close()


@pytest.mark.asyncio
async def test_chat_stream_skips_empty_delta():
    """chat_stream() skips SSE chunks where delta has no content key."""
    client = LLMClient(api_key="test-key")

    sse_lines = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        'data: {"choices":[{"delta":{"content":"OK"}}]}',
        "data: [DONE]",
    ]

    mock_stream_response = MagicMock()
    mock_stream_response.aiter_lines = lambda: AsyncIteratorMock(sse_lines)

    client.http.stream = MagicMock(
        return_value=AsyncContextMock(mock_stream_response)
    )

    chunks = []
    async for chunk in client.chat_stream([{"role": "user", "content": "Hi"}]):
        chunks.append(chunk)

    assert chunks == ["OK"]

    await client.close()


@pytest.mark.asyncio
async def test_chat_json_strips_markdown_fences():
    """chat_json() strips markdown code fences and parses JSON."""
    client = LLMClient(api_key="test-key")

    # Mock chat() to return markdown-fenced JSON
    client.chat = AsyncMock(return_value='```json\n{"key": "value"}\n```')

    result = await client.chat_json([{"role": "user", "content": "Give JSON"}])
    assert result == {"key": "value"}

    # Verify lower temperature was used
    client.chat.assert_called_once_with(
        [{"role": "user", "content": "Give JSON"}], temperature=0.3
    )

    await client.close()


@pytest.mark.asyncio
async def test_chat_json_plain_json():
    """chat_json() parses plain JSON without fences."""
    client = LLMClient(api_key="test-key")

    client.chat = AsyncMock(return_value='[1, 2, 3]')

    result = await client.chat_json([{"role": "user", "content": "Give list"}])
    assert result == [1, 2, 3]

    await client.close()


@pytest.mark.asyncio
async def test_chat_json_fences_no_language_tag():
    """chat_json() strips fences even without a language tag."""
    client = LLMClient(api_key="test-key")

    client.chat = AsyncMock(return_value='```\n{"a": 1}\n```')

    result = await client.chat_json([{"role": "user", "content": "Give JSON"}])
    assert result == {"a": 1}

    await client.close()


@pytest.mark.asyncio
async def test_custom_model():
    """LLMClient can be initialized with a custom model."""
    client = LLMClient(api_key="test-key", model="glm-4-plus")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hi"}}]
    }

    client.http.post = AsyncMock(return_value=mock_response)

    await client.chat([{"role": "user", "content": "Hi"}])

    call_kwargs = client.http.post.call_args
    body = call_kwargs[1]["json"]
    assert body["model"] == "glm-4-plus"

    await client.close()


@pytest.mark.asyncio
async def test_auth_header():
    """LLMClient sets the Authorization bearer header."""
    client = LLMClient(api_key="my-secret-key")

    # The httpx client should have the auth header
    assert client.http.headers["Authorization"] == "Bearer my-secret-key"

    await client.close()
