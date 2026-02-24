"""Handout processor: PDF extraction, LLM parsing, chunking, and vectorization."""

from __future__ import annotations

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into word-based chunks of approximately *chunk_size* words
    with *overlap* word overlap between consecutive chunks."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        if end >= len(words):
            break
        start = end - overlap
    return chunks


PARSE_PROMPT = """You are a course content analyzer. Analyze the following course handout and extract a complete course structure.

Return ONLY valid JSON (no markdown fences) in this exact format:
{
  "name": "Course Name (inferred from the handout content)",
  "description": "A 1-2 sentence description of what this course covers",
  "sections": [
    {
      "title": "Section Title",
      "summary": "Brief section summary",
      "learning_objectives": ["Objective 1", "Objective 2"],
      "key_concepts": ["Concept 1", "Concept 2"],
      "prerequisites": ["Prerequisite 1"],
      "subtopics": [
        {
          "title": "Subtopic Title",
          "content": "Full subtopic content from the handout",
          "summary": "Brief subtopic summary"
        }
      ]
    }
  ]
}

Rules:
- Infer the course name and description from the handout content
- Group related content logically into sections
- Each subtopic should be a focused, teachable unit
- Learning objectives should describe what students will be able to do after studying the section
- Key concepts are the important terms and ideas in the section
- Prerequisites are what students should know before this section

HANDOUT:
"""


class HandoutProcessor:
    """Parse handout text into sections/subtopics, chunk, embed, and index."""

    def __init__(self, db, llm, embedder, vector_store):
        self.db = db
        self.llm = llm
        self.embedder = embedder
        self.vector_store = vector_store

    async def process(self, course_id: str, text: str):
        """Parse handout text into sections/subtopics, chunk, embed, and index.

        Returns a dict with ``name`` and ``description`` auto-extracted from
        the handout content.
        """
        result = await self.llm.chat_json(
            [{"role": "user", "content": PARSE_PROMPT + text}]
        )

        name = result.get("name", "")
        description = result.get("description", "")
        sections = result.get("sections", [])

        for sec_idx, section in enumerate(sections):
            section_id = await self.db.create_section(
                course_id,
                section["title"],
                section.get("summary", ""),
                sec_idx,
                learning_objectives=section.get("learning_objectives", []),
                key_concepts=section.get("key_concepts", []),
                prerequisites=section.get("prerequisites", []),
            )

            for st_idx, subtopic in enumerate(section.get("subtopics", [])):
                subtopic_id = await self.db.create_subtopic(
                    section_id,
                    subtopic["title"],
                    subtopic.get("content", ""),
                    subtopic.get("summary", ""),
                    st_idx,
                )

                content = subtopic.get("content", "")
                if not content:
                    continue
                chunks = chunk_text(content)

                # Store chunks in DB regardless of vector store availability
                for i, chunk_text_val in enumerate(chunks):
                    await self.db.create_chunk(subtopic_id, chunk_text_val, i)

                # Embed and index only if both embedder and vector store are available
                if self.embedder and self.vector_store:
                    embeddings = self.embedder.embed_batch(chunks)
                    batch = []
                    for i, (chunk_text_val, emb) in enumerate(
                        zip(chunks, embeddings)
                    ):
                        batch.append(
                            {
                                "id": f"{subtopic_id}_{i}",
                                "embedding": emb,
                                "subtopic_id": subtopic_id,
                            }
                        )
                    if batch:
                        self.vector_store.add_batch(batch)

        if self.vector_store:
            self.vector_store.optimize()

        return {"name": name, "description": description}
