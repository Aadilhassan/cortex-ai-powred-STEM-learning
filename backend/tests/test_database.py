"""Tests for the SQLite database layer."""

import pytest
import pytest_asyncio
from app.database import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    """Create a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.initialize()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_create_course(db):
    """Create and retrieve a course."""
    course_id = await db.create_course("Math 101", "Intro to math", "raw handout text")
    assert course_id is not None

    course = await db.get_course(course_id)
    assert course is not None
    assert course["id"] == course_id
    assert course["name"] == "Math 101"
    assert course["description"] == "Intro to math"
    assert course["handout_raw"] == "raw handout text"
    assert course["created_at"] is not None

    # Also verify list_courses returns it
    courses = await db.list_courses()
    assert len(courses) == 1
    assert courses[0]["id"] == course_id


@pytest.mark.asyncio
async def test_create_section_and_subtopic(db):
    """Create section under course, subtopic under section, retrieve subtopics."""
    course_id = await db.create_course("Physics", "Intro to physics")

    section_id = await db.create_section(course_id, "Mechanics", "About mechanics", 0)
    assert section_id is not None

    sections = await db.get_sections_by_course(course_id)
    assert len(sections) == 1
    assert sections[0]["title"] == "Mechanics"
    assert sections[0]["summary"] == "About mechanics"
    assert sections[0]["course_id"] == course_id

    subtopic_id = await db.create_subtopic(
        section_id, "Newton's Laws", "F=ma and friends", "Laws of motion", 0
    )
    assert subtopic_id is not None

    subtopic = await db.get_subtopic(subtopic_id)
    assert subtopic is not None
    assert subtopic["title"] == "Newton's Laws"
    assert subtopic["content"] == "F=ma and friends"
    assert subtopic["summary"] == "Laws of motion"

    subtopics = await db.get_subtopics_by_section(section_id)
    assert len(subtopics) == 1
    assert subtopics[0]["id"] == subtopic_id


@pytest.mark.asyncio
async def test_messages(db):
    """Save user + assistant messages, retrieve them, verify diagrams JSON round-trips."""
    course_id = await db.create_course("Bio", "Biology")
    section_id = await db.create_section(course_id, "Cells", "Cell biology", 0)
    subtopic_id = await db.create_subtopic(section_id, "Mitosis", "Cell division", "", 0)

    # Save a user message with no diagrams
    msg1_id = await db.save_message(subtopic_id, "user", "What is mitosis?")
    assert msg1_id is not None

    # Save an assistant message with diagrams
    diagrams = [{"type": "svg", "data": "<svg>...</svg>"}]
    msg2_id = await db.save_message(
        subtopic_id, "assistant", "Mitosis is cell division.", diagrams
    )
    assert msg2_id is not None

    # Retrieve messages
    messages = await db.get_messages(subtopic_id)
    assert len(messages) == 2

    # First message (user) should have empty diagrams list
    user_msg = messages[0]
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "What is mitosis?"
    assert user_msg["diagrams"] == []

    # Second message (assistant) should have diagrams round-tripped
    asst_msg = messages[1]
    assert asst_msg["role"] == "assistant"
    assert asst_msg["content"] == "Mitosis is cell division."
    assert asst_msg["diagrams"] == diagrams
    assert isinstance(asst_msg["diagrams"], list)
    assert asst_msg["diagrams"][0]["type"] == "svg"


@pytest.mark.asyncio
async def test_delete_course_cascades(db):
    """Delete course, verify sections/subtopics also deleted."""
    course_id = await db.create_course("Chemistry", "Intro to chemistry")
    section_id = await db.create_section(course_id, "Atoms", "Atomic theory", 0)
    subtopic_id = await db.create_subtopic(section_id, "Electrons", "e-", "", 0)
    await db.create_chunk(subtopic_id, "Electron content chunk", 0)
    await db.save_message(subtopic_id, "user", "Tell me about electrons")

    # Verify data exists before deletion
    assert await db.get_course(course_id) is not None
    assert len(await db.get_sections_by_course(course_id)) == 1
    assert len(await db.get_subtopics_by_section(section_id)) == 1
    assert len(await db.get_chunks_by_subtopic(subtopic_id)) == 1
    assert len(await db.get_messages(subtopic_id)) == 1

    # Delete course
    await db.delete_course(course_id)

    # Verify everything cascaded
    assert await db.get_course(course_id) is None
    assert len(await db.get_sections_by_course(course_id)) == 0
    assert len(await db.get_subtopics_by_section(section_id)) == 0
    assert len(await db.get_chunks_by_subtopic(subtopic_id)) == 0
    assert len(await db.get_messages(subtopic_id)) == 0


@pytest.mark.asyncio
async def test_upsert_progress(db):
    """Insert then update progress."""
    course_id = await db.create_course("History", "World history")
    section_id = await db.create_section(course_id, "Ancient", "Ancient history", 0)
    subtopic_id = await db.create_subtopic(section_id, "Rome", "Roman empire", "", 0)

    # Insert progress
    await db.upsert_progress(subtopic_id, "in_progress")

    progress = await db.get_course_progress(course_id)
    assert len(progress) == 1
    assert progress[0]["subtopic_id"] == subtopic_id
    assert progress[0]["status"] == "in_progress"

    # Update progress (upsert same subtopic)
    await db.upsert_progress(subtopic_id, "completed")

    progress = await db.get_course_progress(course_id)
    assert len(progress) == 1
    assert progress[0]["status"] == "completed"
