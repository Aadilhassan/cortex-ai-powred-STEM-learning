"""Progress tracking endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["progress"])


@router.get("/progress/{course_id}")
async def get_course_progress(course_id: str, request: Request):
    """Get progress for all subtopics in a course."""
    db = request.app.state.db
    progress = await db.get_course_progress(course_id)
    return progress
