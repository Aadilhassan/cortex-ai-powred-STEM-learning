import pytest
import pytest_asyncio

from app.database import Database
from app.services.embedder import Embedder
from app.services.vector_store import VectorStore, _to_blob


@pytest.fixture(scope="module")
def embedder():
    """Module-scoped real embedder (model loads once for all tests)."""
    return Embedder()


@pytest_asyncio.fixture()
async def db(tmp_path):
    """Create a fresh in-memory database for each test."""
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest_asyncio.fixture()
async def store(db):
    """Create a VectorStore backed by the test database."""
    return VectorStore(db)


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_and_search(db, store, embedder):
    """Add 3 chunks with different content, search for related content,
    verify the most relevant chunk is returned first."""
    # Create course -> section -> subtopic
    course_id = await db.create_course("Test Course")
    section_id = await db.create_section(course_id, "Section 1")
    subtopic_id = await db.create_subtopic(section_id, "Biology Basics")

    texts = [
        "Photosynthesis converts sunlight into chemical energy in plants",
        "The French Revolution began in 1789 with the storming of the Bastille",
        "Mitochondria are the powerhouse of the cell and produce ATP",
    ]
    embeddings = embedder.embed_batch(texts)

    for idx, (text, emb) in enumerate(zip(texts, embeddings)):
        await db.create_chunk_with_embedding(
            subtopic_id, text, _to_blob(emb), idx
        )

    # Search for something related to biology / cells
    query_emb = embedder.embed("cellular energy production")
    results = await store.search(query_emb, topk=3, subtopic_id=subtopic_id)

    assert len(results) >= 1
    # The mitochondria chunk should be the most relevant
    assert "Mitochondria" in results[0]["content"]
    for r in results:
        assert "id" in r
        assert "content" in r
        assert "score" in r


@pytest.mark.asyncio
async def test_search_material_chunks(db, store, embedder):
    """Add material chunks to a course, verify search by course_id works."""
    course_id = await db.create_course("Test Course")
    material_id = await db.create_material(course_id, "notes.txt", "Some notes")

    texts = [
        "Derivatives measure rates of change",
        "Integrals compute areas under curves",
    ]
    embeddings = embedder.embed_batch(texts)

    for i, (text, emb) in enumerate(zip(texts, embeddings)):
        await db.create_material_chunk(
            material_id, course_id, text, _to_blob(emb), i
        )

    query_emb = embedder.embed("mathematical analysis of change")
    results = await store.search(query_emb, topk=2, course_id=course_id)

    assert len(results) == 2
    # Derivatives should be most relevant to "rates of change"
    assert "Derivatives" in results[0]["content"]


@pytest.mark.asyncio
async def test_empty_search(db, store, embedder):
    """Search with no matching chunks returns empty list."""
    query_emb = embedder.embed("quantum physics")
    results = await store.search(query_emb, topk=5, subtopic_id="nonexistent")
    assert results == []
