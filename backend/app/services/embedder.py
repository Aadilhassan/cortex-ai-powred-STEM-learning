from sentence_transformers import SentenceTransformer


class Embedder:
    """Generates 384-dimensional embeddings using a SentenceTransformer model."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector."""
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings into vectors."""
        return self.model.encode(texts).tolist()
