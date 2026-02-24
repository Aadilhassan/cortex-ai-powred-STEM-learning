"""Course CRUD + file upload endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from app.services.handout_processor import extract_text_from_pdf

router = APIRouter(tags=["courses"])


# ── Request / Response models ────────────────────────────────────────────────


class CourseCreate(BaseModel):
    handout_text: str


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_db(request: Request):
    return request.app.state.db


def _get_processor(request: Request):
    return request.app.state.handout_processor


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/courses")
async def create_course(body: CourseCreate, request: Request):
    """Create a course from handout text. Name and description are auto-extracted by the LLM."""
    db = _get_db(request)
    processor = _get_processor(request)

    if not body.handout_text.strip():
        raise HTTPException(status_code=400, detail="Handout text is required")

    course_id = await db.create_course(
        name="Processing...",
        description="",
        handout_raw=body.handout_text,
    )

    try:
        extracted = await processor.process(course_id, body.handout_text)
        await db.update_course(course_id, name=extracted["name"], description=extracted["description"])
    except Exception as e:
        print(f"[courses] Handout processing failed: {e}")
        await db.update_course(course_id, name="Untitled Course")

    course = await db.get_course(course_id)
    return course


@router.post("/courses/upload")
async def create_course_upload(
    request: Request,
    file: UploadFile = File(...),
):
    """Create a course from a file upload (PDF or text). Name and description are auto-extracted."""
    db = _get_db(request)
    processor = _get_processor(request)

    file_bytes = await file.read()

    if file.filename and file.filename.lower().endswith(".pdf"):
        handout_text = extract_text_from_pdf(file_bytes)
    else:
        handout_text = file_bytes.decode("utf-8")

    if not handout_text.strip():
        raise HTTPException(status_code=400, detail="File contains no text")

    course_id = await db.create_course(
        name="Processing...",
        description="",
        handout_raw=handout_text,
    )

    try:
        extracted = await processor.process(course_id, handout_text)
        await db.update_course(course_id, name=extracted["name"], description=extracted["description"])
    except Exception as e:
        print(f"[courses] Handout processing failed: {e}")
        await db.update_course(course_id, name="Untitled Course")

    course = await db.get_course(course_id)
    return course


@router.get("/courses")
async def list_courses(request: Request):
    """List all courses."""
    db = _get_db(request)
    return await db.list_courses()


@router.get("/courses/{course_id}")
async def get_course(course_id: str, request: Request):
    """Get a course with its sections and subtopics tree."""
    db = _get_db(request)

    course = await db.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    sections = await db.get_sections_by_course(course_id)
    section_list = []
    for section in sections:
        subtopics = await db.get_subtopics_by_section(section["id"])
        section_list.append({**section, "subtopics": subtopics})

    return {**course, "sections": section_list}


@router.post("/courses/{course_id}/reprocess")
async def reprocess_course(course_id: str, request: Request):
    """Re-parse the course handout into sections/subtopics."""
    db = _get_db(request)
    processor = _get_processor(request)

    course = await db.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    handout = course.get("handout_raw", "")
    if not handout.strip():
        raise HTTPException(status_code=400, detail="No handout text to process")

    extracted = await processor.process(course_id, handout)
    await db.update_course(course_id, name=extracted["name"], description=extracted["description"])

    course = await db.get_course(course_id)

    # Return updated course with sections
    sections = await db.get_sections_by_course(course_id)
    section_list = []
    for section in sections:
        subtopics = await db.get_subtopics_by_section(section["id"])
        section_list.append({**section, "subtopics": subtopics})

    return {**course, "sections": section_list}


@router.delete("/courses/{course_id}")
async def delete_course(course_id: str, request: Request):
    """Delete a course and all its cascaded data."""
    db = _get_db(request)

    course = await db.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await db.delete_course(course_id)
    return {"status": "deleted"}
