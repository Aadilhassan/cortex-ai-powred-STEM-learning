"""Vector search using numpy cosine similarity over SQLite-stored embeddings."""

from __future__ import annotations

import struct

import numpy as np


def _to_blob(embedding: list[float]) -> bytes:
    """Pack a float32 list into a compact BLOB."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def _from_blob(blob: bytes) -> np.ndarray:
    """Unpack a BLOB back into a numpy float32 array."""
    return np.frombuffer(blob, dtype=np.float32)


class VectorStore:
    """Semantic search over SQLite-stored embeddings using numpy cosine similarity."""

    def __init__(self, db) -> None:
        self.db = db

    async def search(
        self,
        query_embedding: list[float],
        topk: int = 5,
        subtopic_id: str | None = None,
        course_id: str | None = None,
        exam_id: str | None = None,
    ) -> list[dict]:
        """Search for nearest chunks by embedding similarity.

        Args:
            query_embedding: The query vector.
            topk: Number of results to return.
            subtopic_id: Search subtopic chunks.
            course_id: Search course-wide material chunks.
            exam_id: Search exam resource chunks.

        Returns:
            List of dicts with "id", "content", and "score" keys,
            sorted by descending similarity.
        """
        rows: list[dict] = []
        if subtopic_id:
            rows = await self.db.get_chunks_with_embeddings_by_subtopic(subtopic_id)
        elif exam_id:
            rows = await self.db.get_exam_resource_chunks_with_embeddings(exam_id)
        elif course_id:
            rows = await self.db.get_material_chunks_with_embeddings_by_course(course_id)

        if not rows:
            return []

        # Build matrix of stored embeddings
        ids = []
        contents = []
        embeddings = []
        for row in rows:
            if row["embedding"] is None:
                continue
            ids.append(row["id"])
            contents.append(row["content"])
            embeddings.append(_from_blob(row["embedding"]))

        if not embeddings:
            return []

        # Cosine similarity: dot(q, e) / (||q|| * ||e||)
        q = np.array(query_embedding, dtype=np.float32)
        mat = np.stack(embeddings)  # (N, dim)
        q_norm = np.linalg.norm(q)
        mat_norms = np.linalg.norm(mat, axis=1)

        # Avoid division by zero
        denom = q_norm * mat_norms
        denom = np.where(denom == 0, 1.0, denom)

        scores = mat @ q / denom

        # Top-k by descending score
        k = min(topk, len(scores))
        top_indices = np.argpartition(scores, -k)[-k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [
            {"id": ids[i], "content": contents[i], "score": float(scores[i])}
            for i in top_indices
        ]

    async def find_related_materials(
        self, section_id: str, course_id: str, threshold: float = 0.3
    ) -> list[str]:
        """Return material_ids whose chunks are relevant to a section's content.

        Computes max cosine similarity between each material chunk and
        all subtopic chunks in the section. Returns material IDs where
        any chunk exceeds the threshold.
        """
        section_rows = await self.db.get_chunks_with_embeddings_by_section(section_id)
        material_rows = await self.db.get_material_chunks_with_embeddings_by_course(course_id)

        if not section_rows or not material_rows:
            return []

        # Build section embedding matrix
        sec_embs = []
        for r in section_rows:
            if r["embedding"]:
                sec_embs.append(_from_blob(r["embedding"]))
        if not sec_embs:
            return []
        sec_mat = np.stack(sec_embs)  # (S, dim)
        sec_norms = np.linalg.norm(sec_mat, axis=1, keepdims=True)
        sec_norms = np.where(sec_norms == 0, 1.0, sec_norms)
        sec_normed = sec_mat / sec_norms

        # Check each material chunk against section chunks
        # Track which material_ids have at least one relevant chunk
        relevant_material_ids: set[str] = set()
        for r in material_rows:
            if r["embedding"] is None:
                continue
            emb = _from_blob(r["embedding"])
            emb_norm = np.linalg.norm(emb)
            if emb_norm == 0:
                continue
            emb_normed = emb / emb_norm
            # Max similarity to any section chunk
            sims = sec_normed @ emb_normed
            if float(np.max(sims)) >= threshold:
                # Look up material_id for this chunk
                mat_id = await self.db._get_material_id_for_chunk(r["id"])
                if mat_id:
                    relevant_material_ids.add(mat_id)

        return list(relevant_material_ids)

    async def add(self, chunk_id: str, embedding: list[float], **_kwargs):
        """Update embedding on an existing chunk row."""
        await self.db.update_chunk_embedding(chunk_id, _to_blob(embedding))

    async def add_batch(self, items: list[dict]):
        """Update embeddings on existing chunk rows."""
        for item in items:
            await self.db.update_chunk_embedding(item["id"], _to_blob(item["embedding"]))

    async def delete(self, chunk_id: str):
        """No-op — SQLite cascade handles cleanup."""
        pass

    async def delete_by_subtopic(self, subtopic_id: str):
        """No-op — SQLite cascade handles cleanup."""
        pass

    async def optimize(self):
        """No-op — no separate index to optimize."""
        pass
