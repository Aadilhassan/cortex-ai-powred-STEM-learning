import subprocess
import sys

import pytest

# zvec's C++ extension requires specific CPU SIMD instructions (e.g. AVX2).
# Importing it can cause a fatal SIGILL crash, so we probe in a subprocess.
_probe = subprocess.run(
    [sys.executable, "-c", "import zvec"],
    capture_output=True,
    timeout=10,
)
_zvec_available = _probe.returncode == 0
_zvec_reason = "zvec C++ extension unavailable (SIGILL or missing CPU features)"

requires_zvec = pytest.mark.skipif(not _zvec_available, reason=_zvec_reason)

# Embedder only needs sentence-transformers (CPU-safe), import unconditionally.
from app.services.embedder import Embedder


@pytest.fixture(scope="module")
def embedder():
    """Module-scoped real embedder (model loads once for all tests)."""
    return Embedder()


@pytest.fixture()
def store(tmp_path):
    """Create a fresh VectorStore in a temporary directory."""
    from app.services.vector_store import VectorStore

    return VectorStore(path=tmp_path / "test_vectors", dimension=384)


# ── Tests ────────────────────────────────────────────────────────────────


@requires_zvec
def test_add_and_search(store, embedder):
    """Add 3 chunks with different content, search for related content,
    verify the most relevant chunk is returned first."""
    texts = [
        "Photosynthesis converts sunlight into chemical energy in plants",
        "The French Revolution began in 1789 with the storming of the Bastille",
        "Mitochondria are the powerhouse of the cell and produce ATP",
    ]
    embeddings = embedder.embed_batch(texts)

    for idx, (text, emb) in enumerate(zip(texts, embeddings)):
        store.add(chunk_id=f"chunk-{idx}", embedding=emb, subtopic_id="bio")

    # Search for something related to biology / cells
    query_emb = embedder.embed("cellular energy production")
    results = store.search(query_emb, topk=3)

    assert len(results) >= 1
    # The mitochondria chunk (chunk-2) should be the most relevant
    assert results[0]["id"] == "chunk-2"
    # Each result has id and score
    for r in results:
        assert "id" in r
        assert "score" in r


@requires_zvec
def test_search_with_filter(store, embedder):
    """Add chunks with different subtopic_ids, search with filter,
    verify only matching subtopic is returned."""
    items = [
        {
            "id": "math-1",
            "embedding": embedder.embed("Derivatives measure rates of change"),
            "subtopic_id": "calculus",
        },
        {
            "id": "math-2",
            "embedding": embedder.embed("Integrals compute areas under curves"),
            "subtopic_id": "calculus",
        },
        {
            "id": "hist-1",
            "embedding": embedder.embed("World War II ended in 1945"),
            "subtopic_id": "history",
        },
    ]
    store.add_batch(items)

    # Search for calculus-related content but filter to history
    query_emb = embedder.embed("mathematical analysis")
    results = store.search(query_emb, topk=5, subtopic_id="history")

    # Only the history chunk should come back
    assert len(results) == 1
    assert results[0]["id"] == "hist-1"


@requires_zvec
def test_delete(store, embedder):
    """Add a chunk, delete it, verify search returns empty."""
    emb = embedder.embed("Quantum entanglement links distant particles")
    store.add(chunk_id="quantum-1", embedding=emb, subtopic_id="physics")

    # Confirm it is searchable
    results = store.search(emb, topk=1)
    assert len(results) == 1
    assert results[0]["id"] == "quantum-1"

    # Delete and verify it's gone
    store.delete("quantum-1")
    results = store.search(emb, topk=1)
    assert len(results) == 0
