"""Quiz generation and submission endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["quiz"])


# ── Request models ───────────────────────────────────────────────────────────


class QuizGenerateRequest(BaseModel):
    course_id: str
    scope: str  # "course", "topic", "subtopic", or "exam"
    section_id: str | None = None
    subtopic_id: str | None = None
    num_questions: int | None = None
    exam_type: str | None = None  # "midterm" or "comprehensive"


class QuizSubmitRequest(BaseModel):
    answers: list


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_db(request: Request):
    return request.app.state.db


def _get_quiz_generator(request: Request):
    return request.app.state.quiz_generator


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/quiz/generate")
async def generate_quiz(body: QuizGenerateRequest, request: Request):
    """Generate a quiz for a course, section, or subtopic."""
    quiz_gen = _get_quiz_generator(request)

    try:
        # For exams, let the generator use its own defaults unless explicitly overridden
        num_q = body.num_questions if body.num_questions is not None else 5
        quiz_id = await quiz_gen.generate(
            course_id=body.course_id,
            scope=body.scope,
            num_questions=num_q,
            section_id=body.section_id,
            subtopic_id=body.subtopic_id,
            exam_type=body.exam_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[quiz] Generation failed: {e}")
        raise HTTPException(status_code=500, detail="Quiz generation failed. Please try again.")

    db = _get_db(request)
    quiz = await db.get_quiz(quiz_id)
    return quiz


@router.get("/quiz/{quiz_id}")
async def get_quiz(quiz_id: str, request: Request):
    """Get a quiz with its questions."""
    db = _get_db(request)
    quiz = await db.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


@router.post("/quiz/{quiz_id}/submit")
async def submit_quiz(quiz_id: str, body: QuizSubmitRequest, request: Request):
    """Submit answers for a quiz and get scored results."""
    db = _get_db(request)
    quiz_gen = _get_quiz_generator(request)

    quiz = await db.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    score, feedback = await quiz_gen.score(quiz["questions"], body.answers)

    await db.save_quiz_attempt(quiz_id, body.answers, score)

    return {"score": score, "feedback": feedback}
