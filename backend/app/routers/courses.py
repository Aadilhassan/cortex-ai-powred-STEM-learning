"""Course CRUD + file upload endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from app.services.handout_processor import extract_text_from_pdf

router = APIRouter(tags=["courses"])


# ── Request / Response models ────────────────────────────────────────────────


class CourseCreate(BaseModel):
    name: str
    description: str = ""
    handout_text: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_db(request: Request):
    return request.app.state.db


def _get_processor(request: Request):
    return request.app.state.handout_processor


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/courses")
async def create_course(body: CourseCreate, request: Request):
    """Create a course from JSON body with optional handout text."""
    db = _get_db(request)
    processor = _get_processor(request)

    course_id = await db.create_course(
        name=body.name,
        description=body.description,
        handout_raw=body.handout_text,
    )

    if body.handout_text.strip():
        await processor.process(course_id, body.handout_text)

    course = await db.get_course(course_id)
    return course


@router.post("/courses/upload")
async def create_course_upload(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
):
    """Create a course from a file upload (PDF or text)."""
    db = _get_db(request)
    processor = _get_processor(request)

    file_bytes = await file.read()

    if file.filename and file.filename.lower().endswith(".pdf"):
        handout_text = extract_text_from_pdf(file_bytes)
    else:
        handout_text = file_bytes.decode("utf-8")

    course_id = await db.create_course(
        name=name,
        description=description,
        handout_raw=handout_text,
    )

    if handout_text.strip():
        await processor.process(course_id, handout_text)

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


@router.delete("/courses/{course_id}")
async def delete_course(course_id: str, request: Request):
    """Delete a course and all its cascaded data."""
    db = _get_db(request)

    course = await db.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await db.delete_course(course_id)
    return {"status": "deleted"}
