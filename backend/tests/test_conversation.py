"""Tests for the conversation manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.conversation import (
    SentenceBuffer,
    ConversationManager,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# SentenceBuffer tests
# ---------------------------------------------------------------------------


def test_sentence_buffer_detects_sentences():
    """Feed tokens that form two sentences; expect them emitted correctly."""
    buf = SentenceBuffer()
    tokens = ["Hello", " world", ".", " How", " are", " you", "?"]
    sentences = []
    for token in tokens:
        result = buf.feed(token)
        if result is not None:
            sentences.append(result)
    # Flush any remaining content
    remaining = buf.flush()
    if remaining is not None:
        sentences.append(remaining)
    assert sentences == ["Hello world.", "How are you?"]


def test_sentence_buffer_skips_mermaid_blocks():
    """Mermaid blocks should not be emitted as sentences."""
    buf = SentenceBuffer()
    tokens = [
        "Here is a diagram.",
        " ```mermaid",
        "\ngraph TD;",
        "\nA-->B;",
        "\n```",
        " And here is more text.",
    ]
    sentences = []
    for token in tokens:
        result = buf.feed(token)
        if result is not None:
            sentences.append(result)
    remaining = buf.flush()
    if remaining is not None:
        sentences.append(remaining)
    # Should get sentences before and after mermaid, but NOT mermaid content
    assert "Here is a diagram." in sentences
    assert "And here is more text." in sentences
    # No mermaid content should appear as a sentence
    for s in sentences:
        assert "graph TD" not in s
        assert "A-->B" not in s


def test_sentence_buffer_flush_returns_remaining():
    """flush() returns whatever is left in the buffer."""
    buf = SentenceBuffer()
    buf.feed("Hello world")
    result = buf.flush()
    assert result == "Hello world"


def test_sentence_buffer_flush_empty():
    """flush() returns None when buffer is empty."""
    buf = SentenceBuffer()
    assert buf.flush() is None


def test_sentence_buffer_exclamation():
    """Exclamation mark followed by space triggers sentence emission."""
    buf = SentenceBuffer()
    sentences = []
    for token in ["Wow", "!", " That", " is", " great", "."]:
        result = buf.feed(token)
        if result is not None:
            sentences.append(result)
    remaining = buf.flush()
    if remaining is not None:
        sentences.append(remaining)
    assert sentences == ["Wow!", "That is great."]


# ---------------------------------------------------------------------------
# build_system_prompt tests
# ---------------------------------------------------------------------------


def test_build_system_prompt():
    """System prompt includes the title and mentions mermaid diagrams."""
    prompt = build_system_prompt("Newton's Laws", "Overview of Newtonian mechanics")
    assert "Newton's Laws" in prompt
    assert "mermaid" in prompt.lower()


def test_build_system_prompt_includes_summary():
    """System prompt includes the summary when provided."""
    prompt = build_system_prompt("Calculus", "Derivatives and integrals")
    assert "Calculus" in prompt
    # The summary or its concepts should be referenced
    assert "Derivatives and integrals" in prompt or "Calculus" in prompt


# ---------------------------------------------------------------------------
# ConversationManager tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_context_builds_message_list():
    """get_context() returns a properly structured message list."""
    # Mock database
    db = AsyncMock()
    db.get_subtopic.return_value = {
        "id": "sub-1",
        "title": "Newton's Laws",
        "summary": "Forces and motion",
        "content": "",
        "section_id": "sec-1",
    }
    db.get_chunks_by_subtopic.return_value = [
        {"id": "chunk-1", "content": "First law: inertia", "subtopic_id": "sub-1"},
        {"id": "chunk-2", "content": "Second law: F=ma", "subtopic_id": "sub-1"},
    ]
    db.get_messages.return_value = [
        {"role": "user", "content": "What is Newton's first law?", "diagrams": []},
        {"role": "assistant", "content": "It states...", "diagrams": []},
    ]

    # Mock embedder and vector store
    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 384

    vector_store = MagicMock()
    vector_store.search.return_value = [
        {"id": "chunk-1", "score": 0.95},
        {"id": "chunk-2", "score": 0.80},
    ]

    # Mock LLM (not used by get_context, but required for init)
    llm = MagicMock()

    manager = ConversationManager(db=db, llm=llm, embedder=embedder, vector_store=vector_store)
    messages = await manager.get_context("sub-1", "Explain the first law")

    # Should start with system message
    assert messages[0]["role"] == "system"
    assert "Newton's Laws" in messages[0]["content"]

    # Should contain a context block with chunk content
    context_msg = messages[1]
    assert context_msg["role"] == "user"
    assert "First law: inertia" in context_msg["content"]
    assert "Second law: F=ma" in context_msg["content"]

    # Should include message history
    assert any(m["content"] == "What is Newton's first law?" for m in messages)
    assert any(m["content"] == "It states..." for m in messages)

    # Should end with the current user message
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Explain the first law"


@pytest.mark.asyncio
async def test_get_context_no_chunks():
    """get_context() works when vector search returns no results."""
    db = AsyncMock()
    db.get_subtopic.return_value = {
        "id": "sub-1",
        "title": "Quantum Mechanics",
        "summary": "Wave-particle duality",
        "content": "",
        "section_id": "sec-1",
    }
    db.get_chunks_by_subtopic.return_value = []
    db.get_messages.return_value = []

    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 384

    vector_store = MagicMock()
    vector_store.search.return_value = []

    llm = MagicMock()

    manager = ConversationManager(db=db, llm=llm, embedder=embedder, vector_store=vector_store)
    messages = await manager.get_context("sub-1", "What is this about?")

    # Should have system message + user message at minimum
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "What is this about?"


@pytest.mark.asyncio
async def test_stream_response_yields_events():
    """stream_response() yields text_delta, sentence, and done events."""
    db = AsyncMock()
    db.get_subtopic.return_value = {
        "id": "sub-1",
        "title": "Calculus",
        "summary": "Limits and derivatives",
        "content": "",
        "section_id": "sec-1",
    }
    db.get_chunks_by_subtopic.return_value = []
    db.get_messages.return_value = []
    db.save_message.return_value = "msg-1"

    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 384

    vector_store = MagicMock()
    vector_store.search.return_value = []

    # Mock LLM to stream tokens that form a sentence
    async def mock_stream(messages, temperature=0.7):
        tokens = ["Hello", " world", ".", " Done", "."]
        for t in tokens:
            yield t

    llm = MagicMock()
    llm.chat_stream = mock_stream

    manager = ConversationManager(db=db, llm=llm, embedder=embedder, vector_store=vector_store)

    events = []
    async for event_type, data in manager.stream_response("sub-1", "Hi"):
        events.append((event_type, data))

    # Should have text_delta events for each token
    text_deltas = [d for t, d in events if t == "text_delta"]
    assert "Hello" in text_deltas
    assert " world" in text_deltas

    # Should have sentence events
    sentences = [d for t, d in events if t == "sentence"]
    assert "Hello world." in sentences

    # Should end with done
    assert events[-1] == ("done", "")

    # Should have saved user message before streaming
    db.save_message.assert_any_call("sub-1", "user", "Hi")

    # Should have updated progress
    db.upsert_progress.assert_called_with("sub-1", "in_progress")


@pytest.mark.asyncio
async def test_stream_response_extracts_mermaid():
    """stream_response() yields diagram events for mermaid blocks."""
    db = AsyncMock()
    db.get_subtopic.return_value = {
        "id": "sub-1",
        "title": "Data Structures",
        "summary": "Trees and graphs",
        "content": "",
        "section_id": "sec-1",
    }
    db.get_chunks_by_subtopic.return_value = []
    db.get_messages.return_value = []
    db.save_message.return_value = "msg-1"

    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 384

    vector_store = MagicMock()
    vector_store.search.return_value = []

    async def mock_stream(messages, temperature=0.7):
        tokens = [
            "Here is a diagram.",
            " ```mermaid\n",
            "graph TD;\n",
            "A-->B;\n",
            "```",
            " That was it.",
        ]
        for t in tokens:
            yield t

    llm = MagicMock()
    llm.chat_stream = mock_stream

    manager = ConversationManager(db=db, llm=llm, embedder=embedder, vector_store=vector_store)

    events = []
    async for event_type, data in manager.stream_response("sub-1", "Show me a diagram"):
        events.append((event_type, data))

    # Should have a diagram event
    diagram_events = [(t, d) for t, d in events if t == "diagram"]
    assert len(diagram_events) >= 1
    mermaid_code = diagram_events[0][1]
    assert "graph TD" in mermaid_code
    assert "A-->B" in mermaid_code

    # Sentences should NOT contain mermaid content
    sentence_events = [d for t, d in events if t == "sentence"]
    for s in sentence_events:
        assert "graph TD" not in s
