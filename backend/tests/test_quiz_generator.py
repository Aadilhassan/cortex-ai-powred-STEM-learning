"""Tests for the QuizGenerator service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.quiz_generator import QuizGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_QUESTIONS = [
    {
        "type": "mcq",
        "question": "What is Newton's first law?",
        "options": ["Inertia", "F=ma", "Action-Reaction", "Gravity"],
        "correct_answer": "Inertia",
        "explanation": "Newton's first law is the law of inertia.",
    },
    {
        "type": "mcq",
        "question": "What is the unit of force?",
        "options": ["Joule", "Newton", "Watt", "Pascal"],
        "correct_answer": "Newton",
        "explanation": "The SI unit of force is the Newton.",
    },
    {
        "type": "short_answer",
        "question": "What is mass times acceleration?",
        "correct_answer": "Force",
        "explanation": "F = ma is Newton's second law.",
    },
    {
        "type": "diagram",
        "question": "What does this diagram show?",
        "diagram": "graph TD\nA-->B",
        "correct_answer": "Flow",
        "explanation": "It shows a simple flow.",
    },
]


def _make_db_mock():
    db = MagicMock()
    db.get_chunks_by_subtopic = AsyncMock()
    db.get_subtopics_by_section = AsyncMock()
    db.get_sections_by_course = AsyncMock()
    db.create_quiz = AsyncMock()
    return db


def _make_llm_mock():
    llm = MagicMock()
    llm.chat_json = AsyncMock()
    return llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_quiz():
    """Mock db.get_chunks_by_subtopic returns chunks, mock llm.chat_json
    returns questions. Verify db.create_quiz called with correct args and
    generate() returns the quiz_id."""
    db = _make_db_mock()
    llm = _make_llm_mock()

    # db returns two chunks for the subtopic
    db.get_chunks_by_subtopic.return_value = [
        {"id": "c1", "subtopic_id": "st1", "content": "Newton's first law states...", "order_index": 0},
        {"id": "c2", "subtopic_id": "st1", "content": "Newton's second law states...", "order_index": 1},
    ]

    # llm returns quiz questions
    llm.chat_json.return_value = SAMPLE_QUESTIONS[:2]  # 2 MCQ questions

    # db.create_quiz returns a quiz id
    db.create_quiz.return_value = "quiz-123"

    gen = QuizGenerator(db, llm)
    quiz_id = await gen.generate(
        course_id="course-1",
        scope="subtopic",
        num_questions=2,
        subtopic_id="st1",
    )

    assert quiz_id == "quiz-123"

    # Verify db.get_chunks_by_subtopic was called with the subtopic id
    db.get_chunks_by_subtopic.assert_called_once_with("st1")

    # Verify llm.chat_json was called once
    llm.chat_json.assert_called_once()

    # Verify db.create_quiz was called with correct args
    db.create_quiz.assert_called_once_with(
        course_id="course-1",
        scope="subtopic",
        questions=SAMPLE_QUESTIONS[:2],
        section_id=None,
        subtopic_id="st1",
    )


@pytest.mark.asyncio
async def test_generate_quiz_topic_scope():
    """When scope is 'topic', gather chunks from all subtopics in the section."""
    db = _make_db_mock()
    llm = _make_llm_mock()

    db.get_subtopics_by_section.return_value = [
        {"id": "st1", "section_id": "sec1", "title": "Sub1"},
        {"id": "st2", "section_id": "sec1", "title": "Sub2"},
    ]
    db.get_chunks_by_subtopic.side_effect = [
        [{"id": "c1", "content": "Chunk 1"}],
        [{"id": "c2", "content": "Chunk 2"}],
    ]
    llm.chat_json.return_value = SAMPLE_QUESTIONS[:1]
    db.create_quiz.return_value = "quiz-456"

    gen = QuizGenerator(db, llm)
    quiz_id = await gen.generate(
        course_id="course-1",
        scope="topic",
        num_questions=1,
        section_id="sec1",
    )

    assert quiz_id == "quiz-456"
    db.get_subtopics_by_section.assert_called_once_with("sec1")
    assert db.get_chunks_by_subtopic.call_count == 2


@pytest.mark.asyncio
async def test_generate_quiz_course_scope():
    """When scope is 'course', gather chunks from all sections and subtopics."""
    db = _make_db_mock()
    llm = _make_llm_mock()

    db.get_sections_by_course.return_value = [
        {"id": "sec1", "course_id": "course-1", "title": "Section 1"},
    ]
    db.get_subtopics_by_section.return_value = [
        {"id": "st1", "section_id": "sec1", "title": "Sub1"},
    ]
    db.get_chunks_by_subtopic.return_value = [
        {"id": "c1", "content": "Chunk 1"},
    ]
    llm.chat_json.return_value = SAMPLE_QUESTIONS[:1]
    db.create_quiz.return_value = "quiz-789"

    gen = QuizGenerator(db, llm)
    quiz_id = await gen.generate(
        course_id="course-1",
        scope="course",
        num_questions=1,
    )

    assert quiz_id == "quiz-789"
    db.get_sections_by_course.assert_called_once_with("course-1")


@pytest.mark.asyncio
async def test_score_mcq():
    """2 MCQ questions, 1 correct 1 wrong -> 50.0% score, feedback has 2 items."""
    db = _make_db_mock()
    llm = _make_llm_mock()
    gen = QuizGenerator(db, llm)

    questions = [
        {
            "type": "mcq",
            "question": "What is 2+2?",
            "options": ["3", "4", "5", "6"],
            "correct_answer": "4",
            "explanation": "Basic arithmetic.",
        },
        {
            "type": "mcq",
            "question": "What is 3+3?",
            "options": ["5", "6", "7", "8"],
            "correct_answer": "6",
            "explanation": "Basic arithmetic.",
        },
    ]
    answers = ["4", "5"]  # first correct, second wrong

    score, feedback = await gen.score(questions, answers)

    assert score == 50.0
    assert len(feedback) == 2
    assert feedback[0]["correct"] is True
    assert feedback[1]["correct"] is False


@pytest.mark.asyncio
async def test_score_short_answer_case_insensitive():
    """'Force' matches 'force' for short_answer questions."""
    db = _make_db_mock()
    llm = _make_llm_mock()
    gen = QuizGenerator(db, llm)

    questions = [
        {
            "type": "short_answer",
            "question": "What is mass times acceleration?",
            "correct_answer": "Force",
            "explanation": "F = ma.",
        },
    ]
    answers = ["force"]  # lowercase should match "Force"

    score, feedback = await gen.score(questions, answers)

    assert score == 100.0
    assert len(feedback) == 1
    assert feedback[0]["correct"] is True


@pytest.mark.asyncio
async def test_score_diagram_case_insensitive():
    """Diagram answers are also scored case-insensitively."""
    db = _make_db_mock()
    llm = _make_llm_mock()
    gen = QuizGenerator(db, llm)

    questions = [
        {
            "type": "diagram",
            "question": "What does this show?",
            "diagram": "graph TD\nA-->B",
            "correct_answer": "Flow",
            "explanation": "A simple flow.",
        },
    ]
    answers = ["FLOW"]

    score, feedback = await gen.score(questions, answers)

    assert score == 100.0
    assert feedback[0]["correct"] is True


@pytest.mark.asyncio
async def test_score_empty():
    """Scoring with no questions returns 0.0 and empty feedback."""
    db = _make_db_mock()
    llm = _make_llm_mock()
    gen = QuizGenerator(db, llm)

    score, feedback = await gen.score([], [])

    assert score == 0.0
    assert feedback == []
