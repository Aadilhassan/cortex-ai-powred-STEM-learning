from pathlib import Path

import zvec


class VectorStore:
    """In-process vector database backed by zvec for semantic search over chunks."""

    def __init__(self, path: Path, dimension: int = 384):
        schema = zvec.CollectionSchema(
            name="chunks",
            fields=zvec.FieldSchema("subtopic_id", zvec.DataType.STRING),
            vectors=zvec.VectorSchema(
                "embedding", zvec.DataType.VECTOR_FP32, dimension
            ),
        )
        self.collection = zvec.create_and_open(path=str(path), schema=schema)

    def add(self, chunk_id: str, embedding: list[float], subtopic_id: str):
        """Insert a single chunk embedding."""
        self.collection.insert(
            zvec.Doc(
                id=chunk_id,
                vectors={"embedding": embedding},
                fields={"subtopic_id": subtopic_id},
            )
        )

    def add_batch(self, items: list[dict]):
        """Insert multiple chunk embeddings.

        Args:
            items: List of dicts with keys "id", "embedding", "subtopic_id".
        """
        docs = [
            zvec.Doc(
                id=i["id"],
                vectors={"embedding": i["embedding"]},
                fields={"subtopic_id": i["subtopic_id"]},
            )
            for i in items
        ]
        self.collection.insert(docs)

    def search(
        self,
        query_embedding: list[float],
        topk: int = 5,
        subtopic_id: str | None = None,
    ) -> list[dict]:
        """Search for nearest chunks by embedding similarity.

        Args:
            query_embedding: The query vector.
            topk: Number of results to return.
            subtopic_id: Optional filter to restrict results to a subtopic.

        Returns:
            List of dicts with "id" and "score" keys.
        """
        kwargs: dict = {"topk": topk}
        if subtopic_id:
            kwargs["filter"] = f"subtopic_id == '{subtopic_id}'"
        results = self.collection.query(
            zvec.VectorQuery(field_name="embedding", vector=query_embedding),
            **kwargs,
        )
        return [{"id": r.id, "score": r.score} for r in results]

    def delete(self, chunk_id: str):
        """Delete a single chunk by ID."""
        self.collection.delete(ids=chunk_id)

    def delete_by_subtopic(self, subtopic_id: str):
        """Delete all chunks belonging to a subtopic."""
        self.collection.delete_by_filter(
            filter=f"subtopic_id == '{subtopic_id}'"
        )

    def optimize(self):
        """Optimize the underlying collection (merge segments, rebuild index)."""
        self.collection.optimize()
