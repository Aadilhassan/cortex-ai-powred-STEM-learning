"""Course CRUD + file upload + materials endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from app.services.handout_processor import extract_text, chunk_text
from app.services.vector_store import _to_blob

router = APIRouter(tags=["courses"])


# ── Request / Response models ────────────────────────────────────────────────


class CourseCreate(BaseModel):
    handout_text: str


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_db(request: Request):
    return request.app.state.db


def _get_processor(request: Request):
    return request.app.state.handout_processor


def _get_embedder(request: Request):
    return request.app.state.embedder


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
    handout_text = extract_text(file.filename or "upload.txt", file_bytes)

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
    """Get a course with its sections, subtopics tree, and per-section related materials."""
    db = _get_db(request)
    vector_store = request.app.state.vector_store

    course = await db.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get all materials once for lookup
    all_materials = await db.get_materials_by_course(course_id)
    mat_lookup = {m["id"]: m for m in all_materials}

    sections = await db.get_sections_by_course(course_id)
    section_list = []
    for section in sections:
        subtopics = await db.get_subtopics_by_section(section["id"])

        # Compute related materials for this section via vector similarity
        related_materials = []
        if vector_store and all_materials:
            try:
                related_ids = await vector_store.find_related_materials(
                    section["id"], course_id
                )
                related_materials = [
                    {"id": mat_lookup[mid]["id"], "filename": mat_lookup[mid]["filename"]}
                    for mid in related_ids
                    if mid in mat_lookup
                ]
            except Exception:
                pass  # graceful fallback — no related materials

        section_list.append({
            **section,
            "subtopics": subtopics,
            "related_materials": related_materials,
        })

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


# ── Materials ────────────────────────────────────────────────────────────────


@router.post("/courses/{course_id}/materials")
async def upload_materials(
    course_id: str,
    request: Request,
    files: List[UploadFile] = File(...),
):
    """Upload one or more files (PDF/TXT/MD/PPTX/VTT) as supplementary course materials.

    After storing and embedding, the course structure is automatically
    reprocessed to incorporate the new material.
    """
    db = _get_db(request)
    embedder = _get_embedder(request)
    processor = _get_processor(request)

    course = await db.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    created_materials = []

    for file in files:
        file_bytes = await file.read()
        filename = file.filename or "untitled"

        text = extract_text(filename, file_bytes)
        if not text.strip():
            continue  # skip empty files silently

        # Create material record
        material_id = await db.create_material(course_id, filename, text)

        # Chunk and embed
        chunks = chunk_text(text)
        embeddings = None
        if embedder:
            embeddings = await embedder.embed_batch(chunks)

        for i, chunk_content in enumerate(chunks):
            emb_blob = _to_blob(embeddings[i]) if embeddings else None
            await db.create_material_chunk(material_id, course_id, chunk_content, emb_blob, i)

        material = await db.get_material(material_id)
        created_materials.append(material)

    if not created_materials:
        raise HTTPException(status_code=400, detail="No files contained extractable text")

    # Reprocess course structure with combined content (handout + all materials)
    try:
        all_materials = await db.get_materials_by_course(course_id)
        material_texts = []
        for m in all_materials:
            # Fetch full content_text for each material
            full_m = await db.get_material(m["id"])
            if full_m and full_m.get("content_text", "").strip():
                material_texts.append(
                    f"--- Material: {full_m['filename']} ---\n{full_m['content_text']}"
                )

        combined = course.get("handout_raw", "")
        if material_texts:
            combined += "\n\n--- SUPPLEMENTARY MATERIALS ---\n\n" + "\n\n".join(material_texts)

        if combined.strip():
            extracted = await processor.process(course_id, combined)
            await db.update_course(
                course_id, name=extracted["name"], description=extracted["description"]
            )
    except Exception as e:
        print(f"[courses] Course reprocessing after material upload failed: {e}")

    return created_materials


@router.get("/courses/{course_id}/materials")
async def list_materials(course_id: str, request: Request):
    """List all materials for a course."""
    db = _get_db(request)
    return await db.get_materials_by_course(course_id)


@router.get("/materials/{material_id}/content")
async def get_material_content(material_id: str, request: Request):
    """Return the extracted text content for a material."""
    db = _get_db(request)
    material = await db.get_material(material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return {
        "id": material["id"],
        "filename": material["filename"],
        "content_text": material.get("content_text", ""),
    }


@router.delete("/materials/{material_id}")
async def delete_material(material_id: str, request: Request):
    """Delete a material and its chunks (cascade)."""
    db = _get_db(request)

    material = await db.get_material(material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    await db.delete_material(material_id)
    return {"status": "deleted"}
