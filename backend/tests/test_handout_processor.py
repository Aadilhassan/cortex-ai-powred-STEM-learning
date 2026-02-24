"""Tests for the handout processor service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.handout_processor import HandoutProcessor, chunk_text


# ---------------------------------------------------------------------------
# chunk_text tests
# ---------------------------------------------------------------------------


def test_chunk_text():
    """1000 words, chunk_size=100, overlap=20 -> multiple chunks, each <= 120 words."""
    words = [f"word{i}" for i in range(1000)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    for chunk in chunks:
        word_count = len(chunk.split())
        assert word_count <= 120, f"Chunk has {word_count} words, expected <= 120"


def test_chunk_text_short():
    """Short text returns a single chunk."""
    text = "This is a short piece of text."
    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) == 1
    assert chunks[0] == text


# ---------------------------------------------------------------------------
# HandoutProcessor.process tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_handout_creates_sections():
    """Mock LLM returns parsed sections JSON. Verify db.create_section called,
    db.create_subtopic called, db.create_chunk called, vector_store.add_batch called."""

    # -- Mock dependencies --

    mock_llm = AsyncMock()
    mock_llm.chat_json.return_value = [
        {
            "title": "Introduction",
            "summary": "Course intro",
            "subtopics": [
                {
                    "title": "Welcome",
                    "content": " ".join([f"word{i}" for i in range(200)]),
                    "summary": "Welcome summary",
                },
            ],
        },
        {
            "title": "Chapter 1",
            "summary": "First chapter",
            "subtopics": [
                {
                    "title": "Basics",
                    "content": " ".join([f"term{i}" for i in range(150)]),
                    "summary": "Basics summary",
                },
                {
                    "title": "Advanced",
                    "content": " ".join([f"adv{i}" for i in range(100)]),
                    "summary": "Advanced summary",
                },
            ],
        },
    ]

    mock_db = AsyncMock()
    mock_db.create_section.side_effect = ["section-1", "section-2"]
    mock_db.create_subtopic.side_effect = ["subtopic-1", "subtopic-2", "subtopic-3"]
    mock_db.create_chunk.side_effect = lambda *args, **kwargs: f"chunk-{args[2]}"

    mock_embedder = MagicMock()
    mock_embedder.embed_batch.return_value = [[0.1] * 384]  # simplified embedding

    mock_vector_store = MagicMock()

    # -- Run processor --

    processor = HandoutProcessor(
        db=mock_db,
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
    )

    await processor.process("course-123", "Some handout text here")

    # -- Assertions --

    # LLM was called with the parse prompt
    mock_llm.chat_json.assert_called_once()

    # Sections were created (2 sections)
    assert mock_db.create_section.call_count == 2
    mock_db.create_section.assert_any_call("course-123", "Introduction", "Course intro", 0)
    mock_db.create_section.assert_any_call("course-123", "Chapter 1", "First chapter", 1)

    # Subtopics were created (3 subtopics total)
    assert mock_db.create_subtopic.call_count == 3
    mock_db.create_subtopic.assert_any_call(
        "section-1", "Welcome",
        " ".join([f"word{i}" for i in range(200)]),
        "Welcome summary", 0,
    )
    mock_db.create_subtopic.assert_any_call(
        "section-2", "Basics",
        " ".join([f"term{i}" for i in range(150)]),
        "Basics summary", 0,
    )
    mock_db.create_subtopic.assert_any_call(
        "section-2", "Advanced",
        " ".join([f"adv{i}" for i in range(100)]),
        "Advanced summary", 1,
    )

    # Chunks were created (each subtopic has content, so create_chunk is called)
    assert mock_db.create_chunk.call_count >= 3

    # Vector store add_batch was called for each subtopic with content
    assert mock_vector_store.add_batch.call_count == 3

    # Vector store optimize was called once at the end
    mock_vector_store.optimize.assert_called_once()
