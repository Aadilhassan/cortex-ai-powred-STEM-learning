# Study Pal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local-first STEM study companion with real-time voice conversations, AI diagrams, and quizzes.

**Architecture:** Monolith FastAPI backend + Astro SPA frontend. WebSocket for real-time chat streaming. KittenTTS for voice, zvec for vector search, SQLite for persistence.

**Tech Stack:** Python 3.12, FastAPI, KittenTTS, zvec, sentence-transformers, PyMuPDF, Astro, React, Mermaid.js, SQLite

**Constraints:** Python 3.12 required (KittenTTS). No embedding API from Z.ai — use local sentence-transformers (all-MiniLM-L6-v2, 384 dims).

**Z.ai API:** Base `https://api.z.ai/api`, endpoint `POST /paas/v4/chat/completions`, auth `Bearer <key>`, streaming SSE.

---

## Phase 1: Backend Foundation

### Task 1: Initialize Python Backend Project

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/.env.example`

**Step 1: Initialize project with uv**

```bash
cd study-pal
mkdir -p backend/app/routers backend/app/services backend/data/vectors backend/tests
uv init backend --python 3.12
```

**Step 2: Add all dependencies**

```bash
cd backend
uv add fastapi uvicorn[standard] websockets aiosqlite pymupdf httpx sentence-transformers zvec soundfile python-dotenv
uv add kittentts --find-links https://github.com/KittenML/KittenTTS/releases/download/0.8/kittentts-0.8.0-py3-none-any.whl
uv add --dev pytest pytest-asyncio httpx
```

Note: If kittentts wheel install fails via uv, download the wheel manually and install:
```bash
wget https://github.com/KittenML/KittenTTS/releases/download/0.8/kittentts-0.8.0-py3-none-any.whl
uv add kittentts-0.8.0-py3-none-any.whl
```

**Step 3: Create config.py**

```python
# backend/app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "study_pal.db"
VECTOR_DIR = DATA_DIR / "vectors"

ZAI_API_KEY = os.getenv("ZAI_API_KEY", "")
ZAI_BASE_URL = "https://api.z.ai/api"
ZAI_MODEL = os.getenv("ZAI_MODEL", "glm-4.7")

TTS_MODEL = "KittenML/kitten-tts-nano-0.8-int8"
TTS_VOICE = "Bella"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHUNK_SIZE = 500  # tokens
CHUNK_OVERLAP = 50
```

**Step 4: Create minimal FastAPI app**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Study Pal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Step 5: Create .env.example**

```
ZAI_API_KEY=your_key_here
ZAI_MODEL=glm-4.7
```

**Step 6: Verify server starts**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
# GET http://localhost:8000/api/health → {"status": "ok"}
```

**Step 7: Commit**

```bash
git add backend/
git commit -m "feat: initialize backend project with FastAPI and dependencies"
```

---

### Task 2: SQLite Database Schema

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/tests/test_database.py`

**Step 1: Write failing test**

```python
# backend/tests/test_database.py
import pytest
import asyncio
from pathlib import Path
from app.database import Database

@pytest.fixture
async def db(tmp_path):
    d = Database(tmp_path / "test.db")
    await d.initialize()
    yield d
    await d.close()

@pytest.mark.asyncio
async def test_create_course(db):
    course_id = await db.create_course("Physics 101", "Intro physics", "raw handout text")
    course = await db.get_course(course_id)
    assert course["name"] == "Physics 101"

@pytest.mark.asyncio
async def test_create_section_and_subtopic(db):
    cid = await db.create_course("Physics", "", "")
    sid = await db.create_section(cid, "Mechanics", "About mechanics", 0)
    stid = await db.create_subtopic(sid, "Newton's Laws", "Content here", "Summary", 0)
    subtopics = await db.get_subtopics_by_section(sid)
    assert len(subtopics) == 1
    assert subtopics[0]["title"] == "Newton's Laws"

@pytest.mark.asyncio
async def test_messages(db):
    cid = await db.create_course("C", "", "")
    sid = await db.create_section(cid, "S", "", 0)
    stid = await db.create_subtopic(sid, "ST", "", "", 0)
    await db.save_message(stid, "user", "What is force?", [])
    await db.save_message(stid, "assistant", "Force is...", ["graph TD\\nA-->B"])
    msgs = await db.get_messages(stid)
    assert len(msgs) == 2
    assert msgs[1]["role"] == "assistant"
```

**Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_database.py -v
# Expected: FAIL (module not found)
```

**Step 3: Implement database.py**

```python
# backend/app/database.py
import aiosqlite
import json
import uuid
from pathlib import Path
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    handout_raw TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sections (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subtopics (
    id TEXT PRIMARY KEY,
    section_id TEXT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    subtopic_id TEXT NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    subtopic_id TEXT NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    diagrams TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quizzes (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    section_id TEXT,
    subtopic_id TEXT,
    scope TEXT NOT NULL,
    questions TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id TEXT PRIMARY KEY,
    quiz_id TEXT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    answers TEXT DEFAULT '[]',
    score REAL DEFAULT 0,
    completed_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS progress (
    id TEXT PRIMARY KEY,
    subtopic_id TEXT UNIQUE NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'not_started',
    last_active TEXT,
    notes TEXT DEFAULT ''
);
"""


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db = None

    async def initialize(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(SCHEMA)
        await self.db.execute("PRAGMA foreign_keys = ON")
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    def _id(self):
        return str(uuid.uuid4())

    # --- Courses ---
    async def create_course(self, name: str, description: str, handout_raw: str) -> str:
        id = self._id()
        await self.db.execute(
            "INSERT INTO courses (id, name, description, handout_raw) VALUES (?, ?, ?, ?)",
            (id, name, description, handout_raw),
        )
        await self.db.commit()
        return id

    async def get_course(self, id: str) -> dict | None:
        cur = await self.db.execute("SELECT * FROM courses WHERE id = ?", (id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def list_courses(self) -> list[dict]:
        cur = await self.db.execute("SELECT * FROM courses ORDER BY created_at DESC")
        return [dict(r) for r in await cur.fetchall()]

    async def delete_course(self, id: str):
        await self.db.execute("DELETE FROM courses WHERE id = ?", (id,))
        await self.db.commit()

    # --- Sections ---
    async def create_section(self, course_id: str, title: str, summary: str, order_index: int) -> str:
        id = self._id()
        await self.db.execute(
            "INSERT INTO sections (id, course_id, title, summary, order_index) VALUES (?, ?, ?, ?, ?)",
            (id, course_id, title, summary, order_index),
        )
        await self.db.commit()
        return id

    async def get_sections_by_course(self, course_id: str) -> list[dict]:
        cur = await self.db.execute(
            "SELECT * FROM sections WHERE course_id = ? ORDER BY order_index", (course_id,)
        )
        return [dict(r) for r in await cur.fetchall()]

    # --- Subtopics ---
    async def create_subtopic(self, section_id: str, title: str, content: str, summary: str, order_index: int) -> str:
        id = self._id()
        await self.db.execute(
            "INSERT INTO subtopics (id, section_id, title, content, summary, order_index) VALUES (?, ?, ?, ?, ?, ?)",
            (id, section_id, title, content, summary, order_index),
        )
        await self.db.commit()
        return id

    async def get_subtopic(self, id: str) -> dict | None:
        cur = await self.db.execute("SELECT * FROM subtopics WHERE id = ?", (id,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def get_subtopics_by_section(self, section_id: str) -> list[dict]:
        cur = await self.db.execute(
            "SELECT * FROM subtopics WHERE section_id = ? ORDER BY order_index", (section_id,)
        )
        return [dict(r) for r in await cur.fetchall()]

    # --- Chunks ---
    async def create_chunk(self, subtopic_id: str, content: str, order_index: int) -> str:
        id = self._id()
        await self.db.execute(
            "INSERT INTO chunks (id, subtopic_id, content, order_index) VALUES (?, ?, ?, ?)",
            (id, subtopic_id, content, order_index),
        )
        await self.db.commit()
        return id

    async def get_chunks_by_subtopic(self, subtopic_id: str) -> list[dict]:
        cur = await self.db.execute(
            "SELECT * FROM chunks WHERE subtopic_id = ? ORDER BY order_index", (subtopic_id,)
        )
        return [dict(r) for r in await cur.fetchall()]

    # --- Messages ---
    async def save_message(self, subtopic_id: str, role: str, content: str, diagrams: list[str]) -> str:
        id = self._id()
        await self.db.execute(
            "INSERT INTO messages (id, subtopic_id, role, content, diagrams) VALUES (?, ?, ?, ?, ?)",
            (id, subtopic_id, role, content, json.dumps(diagrams)),
        )
        await self.db.commit()
        return id

    async def get_messages(self, subtopic_id: str, limit: int = 50) -> list[dict]:
        cur = await self.db.execute(
            "SELECT * FROM messages WHERE subtopic_id = ? ORDER BY created_at LIMIT ?",
            (subtopic_id, limit),
        )
        rows = [dict(r) for r in await cur.fetchall()]
        for r in rows:
            r["diagrams"] = json.loads(r["diagrams"])
        return rows

    # --- Quizzes ---
    async def create_quiz(self, course_id: str, scope: str, questions: list, section_id: str = None, subtopic_id: str = None) -> str:
        id = self._id()
        await self.db.execute(
            "INSERT INTO quizzes (id, course_id, section_id, subtopic_id, scope, questions) VALUES (?, ?, ?, ?, ?, ?)",
            (id, course_id, section_id, subtopic_id, scope, json.dumps(questions)),
        )
        await self.db.commit()
        return id

    async def get_quiz(self, id: str) -> dict | None:
        cur = await self.db.execute("SELECT * FROM quizzes WHERE id = ?", (id,))
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["questions"] = json.loads(d["questions"])
        return d

    async def save_quiz_attempt(self, quiz_id: str, answers: list, score: float) -> str:
        id = self._id()
        await self.db.execute(
            "INSERT INTO quiz_attempts (id, quiz_id, answers, score) VALUES (?, ?, ?, ?)",
            (id, quiz_id, json.dumps(answers), score),
        )
        await self.db.commit()
        return id

    # --- Progress ---
    async def upsert_progress(self, subtopic_id: str, status: str):
        await self.db.execute(
            """INSERT INTO progress (id, subtopic_id, status, last_active)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(subtopic_id) DO UPDATE SET status = ?, last_active = datetime('now')""",
            (self._id(), subtopic_id, status, status),
        )
        await self.db.commit()

    async def get_course_progress(self, course_id: str) -> list[dict]:
        cur = await self.db.execute(
            """SELECT p.*, st.title as subtopic_title, s.title as section_title
               FROM progress p
               JOIN subtopics st ON p.subtopic_id = st.id
               JOIN sections s ON st.section_id = s.id
               WHERE s.course_id = ?""",
            (course_id,),
        )
        return [dict(r) for r in await cur.fetchall()]
```

**Step 4: Run tests, verify they pass**

```bash
cd backend && uv run pytest tests/test_database.py -v
# Expected: 3 passed
```

**Step 5: Commit**

```bash
git add backend/app/database.py backend/tests/test_database.py
git commit -m "feat: SQLite database layer with full CRUD operations"
```

---

### Task 3: LLM Client (Z.ai API)

**Files:**
- Create: `backend/app/services/llm_client.py`
- Create: `backend/tests/test_llm_client.py`

**Step 1: Write failing test**

```python
# backend/tests/test_llm_client.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_client import LLMClient

@pytest.fixture
def client():
    return LLMClient(api_key="test-key", model="glm-4.7")

@pytest.mark.asyncio
async def test_chat_returns_content(client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}]
    }
    with patch.object(client.http, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello!"

@pytest.mark.asyncio
async def test_chat_stream_yields_chunks(client):
    lines = [
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        b'data: {"choices":[{"delta":{"content":" world"}}]}',
        b'data: [DONE]',
    ]
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.aiter_lines = AsyncMock(return_value=AsyncIteratorMock(lines))

    with patch.object(client.http, "stream", return_value=AsyncContextMock(mock_response)):
        chunks = []
        async for chunk in client.chat_stream([{"role": "user", "content": "Hi"}]):
            chunks.append(chunk)
        assert chunks == ["Hello", " world"]

# Helpers for async mocking
class AsyncIteratorMock:
    def __init__(self, items):
        self.items = iter(items)
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration

class AsyncContextMock:
    def __init__(self, value):
        self.value = value
    async def __aenter__(self):
        return self.value
    async def __aexit__(self, *args):
        pass
```

**Step 2: Run test, verify fail**

```bash
cd backend && uv run pytest tests/test_llm_client.py -v
```

**Step 3: Implement llm_client.py**

```python
# backend/app/services/llm_client.py
import json
import httpx
from typing import AsyncIterator

class LLMClient:
    def __init__(self, api_key: str, model: str = "glm-4.7"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.z.ai/api"
        self.http = httpx.AsyncClient(timeout=60.0)

    async def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """Non-streaming chat completion."""
        resp = await self.http.post(
            f"{self.base_url}/paas/v4/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": temperature},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def chat_stream(self, messages: list[dict], temperature: float = 0.7) -> AsyncIterator[str]:
        """Streaming chat completion. Yields text chunks."""
        async with self.http.stream(
            "POST",
            f"{self.base_url}/paas/v4/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": temperature, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if content:
                    yield content

    async def chat_json(self, messages: list[dict], temperature: float = 0.3) -> dict | list:
        """Chat expecting JSON response. Parses and returns."""
        resp = await self.chat(messages, temperature=temperature)
        # Strip markdown code fences if present
        text = resp.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        return json.loads(text)

    async def close(self):
        await self.http.aclose()
```

**Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/test_llm_client.py -v
```

**Step 5: Commit**

```bash
git add backend/app/services/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat: Z.ai LLM client with streaming and JSON support"
```

---

### Task 4: Embedding Service + Vector Store

**Files:**
- Create: `backend/app/services/embedder.py`
- Create: `backend/app/services/vector_store.py`
- Create: `backend/tests/test_vector_store.py`

**Step 1: Write failing test**

```python
# backend/tests/test_vector_store.py
import pytest
from pathlib import Path
from app.services.vector_store import VectorStore

@pytest.fixture
def store(tmp_path):
    s = VectorStore(tmp_path / "vectors", dimension=384)
    yield s

def test_add_and_search(store):
    # Use real embedder for integration test
    from app.services.embedder import Embedder
    embedder = Embedder()

    emb1 = embedder.embed("Newton's first law of motion states objects at rest stay at rest")
    emb2 = embedder.embed("The mitochondria is the powerhouse of the cell")
    emb3 = embedder.embed("An object in motion stays in motion unless acted upon")

    store.add("chunk_1", emb1, subtopic_id="st_physics")
    store.add("chunk_2", emb2, subtopic_id="st_biology")
    store.add("chunk_3", emb3, subtopic_id="st_physics")
    store.optimize()

    query_emb = embedder.embed("What is Newton's law?")
    results = store.search(query_emb, topk=2)
    ids = [r["id"] for r in results]
    assert "chunk_1" in ids or "chunk_3" in ids

def test_search_with_filter(store):
    from app.services.embedder import Embedder
    embedder = Embedder()

    store.add("c1", embedder.embed("physics concept"), subtopic_id="st_1")
    store.add("c2", embedder.embed("physics concept"), subtopic_id="st_2")
    store.optimize()

    results = store.search(embedder.embed("physics"), topk=5, subtopic_id="st_1")
    assert all(r["id"] == "c1" for r in results)

def test_delete(store):
    from app.services.embedder import Embedder
    embedder = Embedder()

    store.add("c1", embedder.embed("test"), subtopic_id="st_1")
    store.optimize()
    store.delete("c1")
    store.optimize()

    results = store.search(embedder.embed("test"), topk=5)
    assert len(results) == 0
```

**Step 2: Run test, verify fail**

```bash
cd backend && uv run pytest tests/test_vector_store.py -v
```

**Step 3: Implement embedder.py**

```python
# backend/app/services/embedder.py
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL

class Embedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()
```

**Step 4: Implement vector_store.py**

```python
# backend/app/services/vector_store.py
import zvec
from pathlib import Path
from app.config import EMBEDDING_DIM

class VectorStore:
    def __init__(self, path: Path, dimension: int = EMBEDDING_DIM):
        self.path = str(path)
        schema = zvec.CollectionSchema(
            name="chunks",
            fields=[zvec.FieldSchema("subtopic_id", zvec.DataType.STRING)],
            vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, dimension),
        )
        self.collection = zvec.create_and_open(path=self.path, schema=schema)

    def add(self, chunk_id: str, embedding: list[float], subtopic_id: str):
        self.collection.insert([
            zvec.Doc(id=chunk_id, vectors={"embedding": embedding}, fields={"subtopic_id": subtopic_id})
        ])

    def add_batch(self, items: list[dict]):
        """items: [{"id": str, "embedding": list, "subtopic_id": str}]"""
        docs = [
            zvec.Doc(id=item["id"], vectors={"embedding": item["embedding"]}, fields={"subtopic_id": item["subtopic_id"]})
            for item in items
        ]
        self.collection.insert(docs)

    def search(self, query_embedding: list[float], topk: int = 5, subtopic_id: str = None) -> list[dict]:
        kwargs = {"topk": topk}
        if subtopic_id:
            kwargs["filter"] = f"subtopic_id == '{subtopic_id}'"
        results = self.collection.query(
            zvec.VectorQuery("embedding", vector=query_embedding),
            **kwargs,
        )
        return [{"id": r.id, "score": r.score} for r in results]

    def delete(self, chunk_id: str):
        self.collection.delete(ids=chunk_id)

    def delete_by_subtopic(self, subtopic_id: str):
        self.collection.delete_by_filter(filter=f"subtopic_id == '{subtopic_id}'")

    def optimize(self):
        self.collection.optimize()
```

**Step 5: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/test_vector_store.py -v
```

**Step 6: Commit**

```bash
git add backend/app/services/embedder.py backend/app/services/vector_store.py backend/tests/test_vector_store.py
git commit -m "feat: embedding service and zvec vector store"
```

---

### Task 5: TTS Engine

**Files:**
- Create: `backend/app/services/tts_engine.py`
- Create: `backend/tests/test_tts_engine.py`

**Step 1: Write failing test**

```python
# backend/tests/test_tts_engine.py
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from app.services.tts_engine import TTSEngine

@pytest.fixture
def engine():
    with patch("app.services.tts_engine.KittenTTS") as mock_cls:
        mock_model = MagicMock()
        mock_model.generate.return_value = np.zeros(24000, dtype=np.float32)  # 1 sec silence
        mock_cls.return_value = mock_model
        e = TTSEngine()
        yield e

def test_generate_returns_wav_bytes(engine):
    audio_bytes = engine.generate("Hello world")
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0

def test_generate_skips_empty_text(engine):
    result = engine.generate("")
    assert result is None

def test_generate_skips_mermaid(engine):
    result = engine.generate("```mermaid\ngraph TD\nA-->B\n```")
    assert result is None
```

**Step 2: Run test, verify fail**

```bash
cd backend && uv run pytest tests/test_tts_engine.py -v
```

**Step 3: Implement tts_engine.py**

```python
# backend/app/services/tts_engine.py
import io
import re
import soundfile as sf
import numpy as np
from kittentts import KittenTTS
from app.config import TTS_MODEL, TTS_VOICE

class TTSEngine:
    def __init__(self):
        self.model = KittenTTS(TTS_MODEL)
        self.voice = TTS_VOICE

    def generate(self, text: str) -> bytes | None:
        """Generate WAV audio bytes from text. Returns None if text should be skipped."""
        text = text.strip()
        if not text:
            return None
        if re.match(r"^```mermaid", text):
            return None
        audio = self.model.generate(text, voice=self.voice)
        buf = io.BytesIO()
        sf.write(buf, audio, 24000, format="WAV")
        return buf.getvalue()
```

**Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/test_tts_engine.py -v
```

**Step 5: Commit**

```bash
git add backend/app/services/tts_engine.py backend/tests/test_tts_engine.py
git commit -m "feat: KittenTTS engine with WAV output and mermaid skip"
```

---

## Phase 2: Business Logic Services

### Task 6: Handout Processor

**Files:**
- Create: `backend/app/services/handout_processor.py`
- Create: `backend/tests/test_handout_processor.py`

**Step 1: Write failing test**

```python
# backend/tests/test_handout_processor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.handout_processor import HandoutProcessor, extract_text_from_pdf, chunk_text

def test_chunk_text():
    text = "word " * 1000  # ~1000 words
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    # Each chunk should be roughly chunk_size words
    for c in chunks[:-1]:
        assert len(c.split()) <= 120  # some tolerance

def test_chunk_text_short():
    text = "Short text here."
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) == 1
    assert chunks[0] == text

@pytest.mark.asyncio
async def test_process_handout_creates_sections():
    mock_db = AsyncMock()
    mock_db.create_section.return_value = "sec_1"
    mock_db.create_subtopic.return_value = "st_1"
    mock_db.create_chunk.return_value = "chunk_1"

    mock_llm = AsyncMock()
    mock_llm.chat_json.return_value = [
        {
            "title": "Mechanics",
            "summary": "About mechanics",
            "subtopics": [
                {"title": "Force", "content": "Force is mass times acceleration.", "summary": "About force"}
            ]
        }
    ]

    mock_embedder = MagicMock()
    mock_embedder.embed_batch.return_value = [[0.1] * 384]

    mock_vector = MagicMock()

    processor = HandoutProcessor(mock_db, mock_llm, mock_embedder, mock_vector)
    await processor.process("course_1", "Some handout about physics and mechanics.")

    mock_db.create_section.assert_called_once()
    mock_db.create_subtopic.assert_called_once()
    mock_db.create_chunk.assert_called()
    mock_vector.add_batch.assert_called()
```

**Step 2: Run test, verify fail**

```bash
cd backend && uv run pytest tests/test_handout_processor.py -v
```

**Step 3: Implement handout_processor.py**

```python
# backend/app/services/handout_processor.py
import fitz  # PyMuPDF
from pathlib import Path

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
    return chunks

PARSE_PROMPT = """You are a course content analyzer. Parse the following course handout into sections and subtopics.

Return ONLY valid JSON (no markdown fences) in this exact format:
[
  {
    "title": "Section Title",
    "summary": "Brief section summary",
    "subtopics": [
      {
        "title": "Subtopic Title",
        "content": "Full subtopic content from the handout",
        "summary": "Brief subtopic summary"
      }
    ]
  }
]

Group related content logically. Each subtopic should be a focused, teachable unit.

HANDOUT:
"""


class HandoutProcessor:
    def __init__(self, db, llm, embedder, vector_store):
        self.db = db
        self.llm = llm
        self.embedder = embedder
        self.vector_store = vector_store

    async def process(self, course_id: str, text: str):
        """Parse handout text into sections/subtopics, chunk, embed, and index."""
        # Ask LLM to parse into sections
        sections = await self.llm.chat_json(
            [{"role": "user", "content": PARSE_PROMPT + text}]
        )

        for sec_idx, section in enumerate(sections):
            section_id = await self.db.create_section(
                course_id, section["title"], section.get("summary", ""), sec_idx
            )

            for st_idx, subtopic in enumerate(section.get("subtopics", [])):
                subtopic_id = await self.db.create_subtopic(
                    section_id,
                    subtopic["title"],
                    subtopic.get("content", ""),
                    subtopic.get("summary", ""),
                    st_idx,
                )

                # Chunk the subtopic content
                content = subtopic.get("content", "")
                if not content:
                    continue
                chunks = chunk_text(content)

                # Embed all chunks
                embeddings = self.embedder.embed_batch(chunks)

                # Store chunks in DB and vector store
                batch = []
                for i, (chunk_text_val, emb) in enumerate(zip(chunks, embeddings)):
                    chunk_id = await self.db.create_chunk(subtopic_id, chunk_text_val, i)
                    batch.append({"id": chunk_id, "embedding": emb, "subtopic_id": subtopic_id})

                if batch:
                    self.vector_store.add_batch(batch)

        self.vector_store.optimize()
```

**Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/test_handout_processor.py -v
```

**Step 5: Commit**

```bash
git add backend/app/services/handout_processor.py backend/tests/test_handout_processor.py
git commit -m "feat: handout processor with PDF extraction, LLM parsing, chunking, and vectorization"
```

---

### Task 7: Conversation Manager

**Files:**
- Create: `backend/app/services/conversation.py`
- Create: `backend/tests/test_conversation.py`

**Step 1: Write failing test**

```python
# backend/tests/test_conversation.py
import pytest
from app.services.conversation import SentenceBuffer, build_system_prompt

def test_sentence_buffer_detects_sentences():
    buf = SentenceBuffer()
    results = []
    for token in ["Hello", " world", ".", " How", " are", " you", "?"]:
        sentence = buf.feed(token)
        if sentence:
            results.append(sentence)
    results.append(buf.flush())  # Get remaining
    results = [r for r in results if r]
    assert results == ["Hello world.", "How are you?"]

def test_sentence_buffer_skips_mermaid_blocks():
    buf = SentenceBuffer()
    results = []
    tokens = ["Here", " is", " a", " diagram", ".", " ```", "mermaid", "\n", "graph", " TD", "\n", "A", "-->", "B", "\n", "```", " And", " more", "."]
    for t in tokens:
        s = buf.feed(t)
        if s:
            results.append(s)
    results.append(buf.flush())
    results = [r for r in results if r]
    # Should have sentences but NOT the mermaid block
    assert any("diagram" in r for r in results)
    assert not any("graph TD" in r for r in results)

def test_build_system_prompt():
    prompt = build_system_prompt("Newton's Laws", "About Newton's laws of motion")
    assert "Newton's Laws" in prompt
    assert "mermaid" in prompt.lower() or "Mermaid" in prompt
```

**Step 2: Run test, verify fail**

```bash
cd backend && uv run pytest tests/test_conversation.py -v
```

**Step 3: Implement conversation.py**

```python
# backend/app/services/conversation.py
import re

SYSTEM_PROMPT_TEMPLATE = """You are a STEM tutor helping a student study "{title}".

Context: {summary}

Instructions:
- Explain concepts clearly with examples
- When explaining structural, visual, or process-based concepts, proactively create Mermaid diagrams
- Wrap all diagrams in ```mermaid ... ``` code blocks
- Supported diagram types: flowchart, sequence, class, state, ER, mindmap
- Ask follow-up questions to check understanding
- Be encouraging and patient
- Keep explanations focused on this subtopic

Relevant course material will be provided in [CONTEXT] blocks. Use them to ground your explanations."""


def build_system_prompt(title: str, summary: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(title=title, summary=summary)


class SentenceBuffer:
    """Accumulates streaming tokens and emits complete sentences, skipping mermaid blocks."""

    def __init__(self):
        self.buffer = ""
        self.in_mermaid = False

    def feed(self, token: str) -> str | None:
        self.buffer += token

        # Track mermaid code block state
        if "```mermaid" in self.buffer and not self.in_mermaid:
            # Emit everything before the mermaid block as a sentence
            before = self.buffer.split("```mermaid")[0].strip()
            self.buffer = self.buffer[self.buffer.index("```mermaid"):]
            self.in_mermaid = True
            if before and before[-1] in ".?!":
                return before
            elif before:
                return before + "."
            return None

        if self.in_mermaid:
            # Look for closing ```
            if self.buffer.count("```") >= 2:
                # Mermaid block complete, discard it
                after_close = self.buffer.split("```", 2)
                if len(after_close) > 2:
                    self.buffer = after_close[2]
                else:
                    self.buffer = ""
                self.in_mermaid = False
            return None

        # Check for sentence endings
        match = re.search(r'[.?!]\s', self.buffer)
        if match:
            end = match.end()
            sentence = self.buffer[:end].strip()
            self.buffer = self.buffer[end:]
            return sentence

        return None

    def flush(self) -> str | None:
        text = self.buffer.strip()
        self.buffer = ""
        self.in_mermaid = False
        return text if text else None


class ConversationManager:
    """Manages a conversation session for a subtopic."""

    def __init__(self, db, llm, embedder, vector_store):
        self.db = db
        self.llm = llm
        self.embedder = embedder
        self.vector_store = vector_store

    async def get_context(self, subtopic_id: str, user_message: str) -> list[dict]:
        """Build full message context for LLM."""
        subtopic = await self.db.get_subtopic(subtopic_id)
        if not subtopic:
            raise ValueError(f"Subtopic {subtopic_id} not found")

        # System prompt
        messages = [{"role": "system", "content": build_system_prompt(subtopic["title"], subtopic["summary"])}]

        # Vector search for relevant chunks
        query_emb = self.embedder.embed(user_message)
        results = self.vector_store.search(query_emb, topk=5, subtopic_id=subtopic_id)

        if results:
            chunk_ids = [r["id"] for r in results]
            chunks = []
            for cid in chunk_ids:
                # Fetch chunk content from DB
                all_chunks = await self.db.get_chunks_by_subtopic(subtopic_id)
                for c in all_chunks:
                    if c["id"] in chunk_ids:
                        chunks.append(c["content"])
            if chunks:
                context = "\n\n".join(chunks)
                messages.append({"role": "system", "content": f"[CONTEXT]\n{context}\n[/CONTEXT]"})

        # Load conversation history (last 20 messages)
        history = await self.db.get_messages(subtopic_id, limit=20)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        return messages

    async def stream_response(self, subtopic_id: str, user_message: str):
        """Stream LLM response. Yields (type, data) tuples.

        Types: "text_delta", "sentence", "diagram", "done"
        """
        # Save user message
        await self.db.save_message(subtopic_id, "user", user_message, [])
        await self.db.upsert_progress(subtopic_id, "in_progress")

        # Build context
        messages = await self.get_context(subtopic_id, user_message)

        full_response = ""
        diagrams = []
        sentence_buf = SentenceBuffer()

        async for token in self.llm.chat_stream(messages):
            full_response += token
            yield ("text_delta", token)

            # Check for complete sentences (for TTS)
            sentence = sentence_buf.feed(token)
            if sentence:
                yield ("sentence", sentence)

        # Flush remaining text
        remaining = sentence_buf.flush()
        if remaining:
            yield ("sentence", remaining)

        # Extract mermaid diagrams from full response
        mermaid_pattern = r"```mermaid\n(.*?)```"
        diagrams = re.findall(mermaid_pattern, full_response, re.DOTALL)
        for d in diagrams:
            yield ("diagram", d.strip())

        # Save assistant message
        await self.db.save_message(subtopic_id, "assistant", full_response, diagrams)

        yield ("done", "")
```

**Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/test_conversation.py -v
```

**Step 5: Commit**

```bash
git add backend/app/services/conversation.py backend/tests/test_conversation.py
git commit -m "feat: conversation manager with sentence streaming and mermaid extraction"
```

---

### Task 8: Quiz Generator

**Files:**
- Create: `backend/app/services/quiz_generator.py`
- Create: `backend/tests/test_quiz_generator.py`

**Step 1: Write failing test**

```python
# backend/tests/test_quiz_generator.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.quiz_generator import QuizGenerator

@pytest.mark.asyncio
async def test_generate_quiz():
    mock_db = AsyncMock()
    mock_db.get_chunks_by_subtopic.return_value = [
        {"content": "Force equals mass times acceleration. F=ma is Newton's second law."},
    ]
    mock_db.create_quiz.return_value = "quiz_1"

    mock_llm = AsyncMock()
    mock_llm.chat_json.return_value = [
        {
            "type": "mcq",
            "question": "What is Newton's second law?",
            "options": ["F=ma", "E=mc2", "V=IR", "P=IV"],
            "correct_answer": "F=ma",
            "explanation": "Newton's second law states F=ma"
        }
    ]

    gen = QuizGenerator(mock_db, mock_llm)
    quiz_id = await gen.generate(
        course_id="c1", scope="subtopic", subtopic_id="st1", num_questions=5
    )
    assert quiz_id == "quiz_1"
    mock_llm.chat_json.assert_called_once()

@pytest.mark.asyncio
async def test_score_mcq():
    gen = QuizGenerator(AsyncMock(), AsyncMock())
    questions = [
        {"type": "mcq", "question": "Q1", "correct_answer": "A"},
        {"type": "mcq", "question": "Q2", "correct_answer": "B"},
    ]
    answers = ["A", "C"]
    score, feedback = await gen.score(questions, answers)
    assert score == 50.0
    assert len(feedback) == 2
```

**Step 2: Run test, verify fail**

```bash
cd backend && uv run pytest tests/test_quiz_generator.py -v
```

**Step 3: Implement quiz_generator.py**

```python
# backend/app/services/quiz_generator.py

QUIZ_PROMPT = """Generate exactly {num} quiz questions based on this study material.

Mix these question types:
- "mcq": Multiple choice (4 options, one correct)
- "short_answer": Short written answer
- "diagram": Include a Mermaid diagram and ask a question about it

Return ONLY valid JSON array:
[
  {{
    "type": "mcq",
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "correct_answer": "A",
    "explanation": "..."
  }},
  {{
    "type": "short_answer",
    "question": "...",
    "correct_answer": "...",
    "explanation": "..."
  }},
  {{
    "type": "diagram",
    "question": "...",
    "diagram": "graph TD\\nA-->B",
    "correct_answer": "...",
    "explanation": "..."
  }}
]

MATERIAL:
{content}
"""


class QuizGenerator:
    def __init__(self, db, llm):
        self.db = db
        self.llm = llm

    async def _gather_content(self, scope: str, course_id: str = None, section_id: str = None, subtopic_id: str = None) -> str:
        if scope == "subtopic" and subtopic_id:
            chunks = await self.db.get_chunks_by_subtopic(subtopic_id)
            return "\n\n".join(c["content"] for c in chunks)

        if scope == "topic" and section_id:
            subtopics = await self.db.get_subtopics_by_section(section_id)
            all_text = []
            for st in subtopics:
                chunks = await self.db.get_chunks_by_subtopic(st["id"])
                all_text.extend(c["content"] for c in chunks)
            return "\n\n".join(all_text)

        if scope == "course" and course_id:
            sections = await self.db.get_sections_by_course(course_id)
            all_text = []
            for sec in sections:
                subtopics = await self.db.get_subtopics_by_section(sec["id"])
                for st in subtopics:
                    chunks = await self.db.get_chunks_by_subtopic(st["id"])
                    all_text.extend(c["content"] for c in chunks)
            return "\n\n".join(all_text)

        return ""

    async def generate(self, course_id: str, scope: str, num_questions: int = 5,
                       section_id: str = None, subtopic_id: str = None) -> str:
        content = await self._gather_content(scope, course_id, section_id, subtopic_id)
        prompt = QUIZ_PROMPT.format(num=num_questions, content=content)
        questions = await self.llm.chat_json([{"role": "user", "content": prompt}])

        quiz_id = await self.db.create_quiz(
            course_id, scope, questions,
            section_id=section_id, subtopic_id=subtopic_id
        )
        return quiz_id

    async def score(self, questions: list[dict], answers: list) -> tuple[float, list[dict]]:
        """Score quiz answers. Returns (percentage, feedback_per_question)."""
        correct = 0
        feedback = []
        for q, a in zip(questions, answers):
            if q["type"] == "mcq":
                is_correct = a == q["correct_answer"]
            elif q["type"] == "short_answer":
                # Use LLM to evaluate short answers
                is_correct = a.strip().lower() == q["correct_answer"].strip().lower()
                # TODO: Use LLM for fuzzy matching in future
            elif q["type"] == "diagram":
                is_correct = a.strip().lower() == q["correct_answer"].strip().lower()
            else:
                is_correct = False

            if is_correct:
                correct += 1
            feedback.append({
                "question": q["question"],
                "your_answer": a,
                "correct_answer": q["correct_answer"],
                "is_correct": is_correct,
                "explanation": q.get("explanation", ""),
            })

        score = (correct / len(questions) * 100) if questions else 0
        return score, feedback
```

**Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/test_quiz_generator.py -v
```

**Step 5: Commit**

```bash
git add backend/app/services/quiz_generator.py backend/tests/test_quiz_generator.py
git commit -m "feat: quiz generator with MCQ, short-answer, and diagram question types"
```

---

## Phase 3: API Routes

### Task 9: Wire Up App + Course Endpoints

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/routers/courses.py`
- Create: `backend/tests/test_api_courses.py`

**Step 1: Write failing test**

```python
# backend/tests/test_api_courses.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_create_and_list_courses(client):
    r = await client.post("/api/courses", json={"name": "Physics 101", "description": "Intro", "handout_text": "Newton discovered gravity."})
    assert r.status_code == 200
    data = r.json()
    assert "id" in data

    r = await client.get("/api/courses")
    assert r.status_code == 200
    courses = r.json()
    assert len(courses) >= 1
```

**Step 2: Run test, verify fail**

```bash
cd backend && uv run pytest tests/test_api_courses.py -v
```

**Step 3: Update main.py to wire DB and services on startup**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import DB_PATH, VECTOR_DIR, ZAI_API_KEY, ZAI_MODEL, DATA_DIR
from app.database import Database
from app.services.llm_client import LLMClient
from app.services.embedder import Embedder
from app.services.vector_store import VectorStore
from app.services.tts_engine import TTSEngine
from app.services.handout_processor import HandoutProcessor
from app.services.conversation import ConversationManager
from app.services.quiz_generator import QuizGenerator

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    db = Database(DB_PATH)
    await db.initialize()
    llm = LLMClient(api_key=ZAI_API_KEY, model=ZAI_MODEL)
    embedder = Embedder()
    vector_store = VectorStore(VECTOR_DIR)
    tts = TTSEngine()

    app.state.db = db
    app.state.llm = llm
    app.state.embedder = embedder
    app.state.vector_store = vector_store
    app.state.tts = tts
    app.state.handout_processor = HandoutProcessor(db, llm, embedder, vector_store)
    app.state.conversation = ConversationManager(db, llm, embedder, vector_store)
    app.state.quiz_generator = QuizGenerator(db, llm)

    yield

    # Shutdown
    await llm.close()
    await db.close()

app = FastAPI(title="Study Pal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from app.routers import courses, quiz, progress
app.include_router(courses.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
app.include_router(progress.router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Step 4: Implement courses router**

```python
# backend/app/routers/courses.py
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from app.services.handout_processor import extract_text_from_pdf

router = APIRouter()

@router.post("/courses")
async def create_course(request: Request):
    body = await request.json()
    db = request.app.state.db
    processor = request.app.state.handout_processor

    name = body.get("name", "Untitled Course")
    description = body.get("description", "")
    handout_text = body.get("handout_text", "")

    course_id = await db.create_course(name, description, handout_text)

    if handout_text:
        await processor.process(course_id, handout_text)

    return {"id": course_id}

@router.post("/courses/upload")
async def create_course_with_file(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
):
    db = request.app.state.db
    processor = request.app.state.handout_processor

    content = await file.read()
    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(content)
    else:
        text = content.decode("utf-8")

    course_id = await db.create_course(name, description, text)
    await processor.process(course_id, text)
    return {"id": course_id}

@router.get("/courses")
async def list_courses(request: Request):
    return await request.app.state.db.list_courses()

@router.get("/courses/{course_id}")
async def get_course(request: Request, course_id: str):
    db = request.app.state.db
    course = await db.get_course(course_id)
    if not course:
        raise HTTPException(404, "Course not found")

    sections = await db.get_sections_by_course(course_id)
    for sec in sections:
        sec["subtopics"] = await db.get_subtopics_by_section(sec["id"])

    course["sections"] = sections
    return course

@router.delete("/courses/{course_id}")
async def delete_course(request: Request, course_id: str):
    await request.app.state.db.delete_course(course_id)
    return {"ok": True}
```

**Step 5: Create stub routers for quiz and progress**

```python
# backend/app/routers/quiz.py
from fastapi import APIRouter
router = APIRouter()

# backend/app/routers/progress.py
from fastapi import APIRouter
router = APIRouter()
```

Make sure `__init__.py` exists in routers:

```python
# backend/app/routers/__init__.py
```

**Step 6: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/test_api_courses.py -v
```

Note: This test may require adjusting the lifespan to support test mode (use tmp dirs). If it fails due to TTS model loading, add an env check:

```python
# In main.py lifespan, add:
import os
if os.getenv("TESTING"):
    tts = None
else:
    tts = TTSEngine()
app.state.tts = tts
```

**Step 7: Commit**

```bash
git add backend/app/main.py backend/app/routers/ backend/tests/test_api_courses.py
git commit -m "feat: course CRUD endpoints with file upload and handout processing"
```

---

### Task 10: WebSocket Conversation Endpoint

**Files:**
- Modify: `backend/app/main.py` (add WS route)
- Create: `backend/app/routers/chat.py`

**Step 1: Implement chat WebSocket**

```python
# backend/app/routers/chat.py
import json
import base64
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws/chat/{subtopic_id}")
async def chat_ws(websocket: WebSocket, subtopic_id: str):
    await websocket.accept()
    app = websocket.app
    conversation = app.state.conversation
    tts = app.state.tts

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("content", "")

            if not user_message:
                continue

            async for event_type, event_data in conversation.stream_response(subtopic_id, user_message):
                if event_type == "text_delta":
                    await websocket.send_json({"type": "text_delta", "content": event_data})

                elif event_type == "sentence":
                    # Generate TTS in background
                    if tts and event_data:
                        audio_bytes = await asyncio.to_thread(tts.generate, event_data)
                        if audio_bytes:
                            audio_b64 = base64.b64encode(audio_bytes).decode()
                            await websocket.send_json({"type": "audio_chunk", "data": audio_b64})

                elif event_type == "diagram":
                    await websocket.send_json({"type": "diagram", "mermaid": event_data})

                elif event_type == "done":
                    await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
```

**Step 2: Add to main.py**

Add this import and include in `main.py`:

```python
from app.routers import courses, quiz, progress, chat
app.include_router(chat.router)
```

**Step 3: Commit**

```bash
git add backend/app/routers/chat.py backend/app/main.py
git commit -m "feat: WebSocket conversation endpoint with streaming TTS"
```

---

### Task 11: Quiz and Progress Endpoints

**Files:**
- Modify: `backend/app/routers/quiz.py`
- Modify: `backend/app/routers/progress.py`

**Step 1: Implement quiz router**

```python
# backend/app/routers/quiz.py
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.post("/quiz/generate")
async def generate_quiz(request: Request):
    body = await request.json()
    gen = request.app.state.quiz_generator

    quiz_id = await gen.generate(
        course_id=body["course_id"],
        scope=body["scope"],
        num_questions=body.get("num_questions", 5),
        section_id=body.get("section_id"),
        subtopic_id=body.get("subtopic_id"),
    )
    return {"id": quiz_id}

@router.get("/quiz/{quiz_id}")
async def get_quiz(request: Request, quiz_id: str):
    quiz = await request.app.state.db.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    return quiz

@router.post("/quiz/{quiz_id}/submit")
async def submit_quiz(request: Request, quiz_id: str):
    body = await request.json()
    db = request.app.state.db
    gen = request.app.state.quiz_generator

    quiz = await db.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")

    answers = body.get("answers", [])
    score, feedback = await gen.score(quiz["questions"], answers)
    attempt_id = await db.save_quiz_attempt(quiz_id, answers, score)

    return {"attempt_id": attempt_id, "score": score, "feedback": feedback}
```

**Step 2: Implement progress router**

```python
# backend/app/routers/progress.py
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/progress/{course_id}")
async def get_progress(request: Request, course_id: str):
    return await request.app.state.db.get_course_progress(course_id)
```

**Step 3: Commit**

```bash
git add backend/app/routers/quiz.py backend/app/routers/progress.py
git commit -m "feat: quiz generation/submission and progress endpoints"
```

---

## Phase 4: Frontend

### Task 12: Initialize Astro Project

**Step 1: Create Astro project**

```bash
cd study-pal
npm create astro@latest frontend -- --template minimal --install --no-git
cd frontend
npx astro add react
npm install mermaid marked
```

**Step 2: Configure astro.config.mjs**

```javascript
// frontend/astro.config.mjs
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

export default defineConfig({
  integrations: [react()],
  server: { port: 4321 },
  vite: {
    server: {
      proxy: {
        '/api': 'http://localhost:8000',
        '/ws': { target: 'ws://localhost:8000', ws: true },
      }
    }
  }
});
```

**Step 3: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Astro frontend with React integration"
```

---

### Task 13: Frontend API + WebSocket Clients

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/websocket.ts`

**Step 1: Implement API client**

```typescript
// frontend/src/lib/api.ts
const BASE = '/api';

export async function listCourses() {
  const r = await fetch(`${BASE}/courses`);
  return r.json();
}

export async function getCourse(id: string) {
  const r = await fetch(`${BASE}/courses/${id}`);
  return r.json();
}

export async function createCourse(name: string, description: string, handoutText: string) {
  const r = await fetch(`${BASE}/courses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description, handout_text: handoutText }),
  });
  return r.json();
}

export async function uploadCourse(name: string, description: string, file: File) {
  const form = new FormData();
  form.append('name', name);
  form.append('description', description);
  form.append('file', file);
  const r = await fetch(`${BASE}/courses/upload`, { method: 'POST', body: form });
  return r.json();
}

export async function deleteCourse(id: string) {
  await fetch(`${BASE}/courses/${id}`, { method: 'DELETE' });
}

export async function generateQuiz(courseId: string, scope: string, opts?: { sectionId?: string; subtopicId?: string; numQuestions?: number }) {
  const r = await fetch(`${BASE}/quiz/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ course_id: courseId, scope, section_id: opts?.sectionId, subtopic_id: opts?.subtopicId, num_questions: opts?.numQuestions ?? 5 }),
  });
  return r.json();
}

export async function getQuiz(id: string) {
  const r = await fetch(`${BASE}/quiz/${id}`);
  return r.json();
}

export async function submitQuiz(quizId: string, answers: string[]) {
  const r = await fetch(`${BASE}/quiz/${quizId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });
  return r.json();
}

export async function getProgress(courseId: string) {
  const r = await fetch(`${BASE}/progress/${courseId}`);
  return r.json();
}
```

**Step 2: Implement WebSocket client**

```typescript
// frontend/src/lib/websocket.ts
export type WSMessage =
  | { type: 'text_delta'; content: string }
  | { type: 'audio_chunk'; data: string }
  | { type: 'diagram'; mermaid: string }
  | { type: 'done' };

export class StudySocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnect = 5;

  constructor(
    private subtopicId: string,
    private onMessage: (msg: WSMessage) => void,
    private onConnect?: () => void,
    private onDisconnect?: () => void,
  ) {}

  connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(`${protocol}//${location.host}/ws/chat/${this.subtopicId}`);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.onConnect?.();
    };

    this.ws.onmessage = (e) => {
      const msg: WSMessage = JSON.parse(e.data);
      this.onMessage(msg);
    };

    this.ws.onclose = () => {
      this.onDisconnect?.();
      if (this.reconnectAttempts < this.maxReconnect) {
        const delay = Math.pow(2, this.reconnectAttempts) * 1000;
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), delay);
      }
    };
  }

  send(content: string) {
    this.ws?.send(JSON.stringify({ content }));
  }

  disconnect() {
    this.maxReconnect = 0;
    this.ws?.close();
  }
}
```

**Step 3: Commit**

```bash
git add frontend/src/lib/
git commit -m "feat: API and WebSocket client libraries"
```

---

### Task 14: Layout and Dashboard Page

**Files:**
- Create: `frontend/src/layouts/Layout.astro`
- Modify: `frontend/src/pages/index.astro`
- Create: `frontend/src/components/CreateCourse.tsx`

**Step 1: Create layout**

```astro
---
// frontend/src/layouts/Layout.astro
const { title = "Study Pal" } = Astro.props;
---
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style is:global>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; background: #0f0f13; color: #e0e0e0; }
    a { color: #7c8aff; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <nav style="padding: 1rem 2rem; border-bottom: 1px solid #222; display: flex; align-items: center; gap: 2rem;">
    <a href="/" style="font-size: 1.2rem; font-weight: bold; color: #fff;">Study Pal</a>
  </nav>
  <main style="padding: 2rem; max-width: 1200px; margin: 0 auto;">
    <slot />
  </main>
</body>
</html>
```

**Step 2: Create dashboard page**

```astro
---
// frontend/src/pages/index.astro
import Layout from '../layouts/Layout.astro';
import CreateCourse from '../components/CreateCourse.tsx';
---
<Layout title="Dashboard - Study Pal">
  <h1 style="margin-bottom: 1.5rem;">Your Courses</h1>
  <CreateCourse client:load />
</Layout>
```

**Step 3: Create CreateCourse component** — This React island handles course list display and creation with file upload. Implementation will include:
- Course cards grid showing all courses
- "New Course" modal with name, description, and file upload / text paste
- Drop zone for PDF/text files
- Calls API to create course, then redirects to course page

The full component code is in the implementation — it's a standard React component with `useState`, `useEffect`, fetch calls to the API client, and a file drop zone using `onDragOver`/`onDrop`.

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: layout and dashboard page with course creation"
```

---

### Task 15: Course Overview Page

**Files:**
- Create: `frontend/src/pages/course/[id].astro`
- Create: `frontend/src/components/SectionTree.tsx`

**Step 1: Create course page**

The course page fetches course data client-side and renders a `SectionTree` React island showing:
- Course name and description at top
- Sections as expandable groups
- Subtopics as clickable items within each section
- Progress indicator per subtopic (not started / in progress / completed)
- "Start Studying" button linking to `/study/:subtopicId`
- "Generate Quiz" buttons at section and course level

**Step 2: Commit**

```bash
git add frontend/src/pages/course/ frontend/src/components/SectionTree.tsx
git commit -m "feat: course overview page with section/subtopic tree"
```

---

### Task 16: Conversation View (THE CORE PAGE)

**Files:**
- Create: `frontend/src/pages/study/[subtopicId].astro`
- Create: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/DiagramPanel.tsx`
- Create: `frontend/src/components/AudioController.tsx`
- Create: `frontend/src/components/VoiceInput.tsx`
- Create: `frontend/src/components/StudyView.tsx`

**This is the most important page.** The `StudyView.tsx` React island orchestrates:

1. **WebSocket connection** via `StudySocket`
2. **ChatPanel** — scrollable message list, markdown rendering (via `marked`), streaming text display
3. **DiagramPanel** — collapsible right panel, renders Mermaid diagrams using `mermaid.run()`, stores diagram history
4. **VoiceInput** — Button that toggles `webkitSpeechRecognition` / `SpeechRecognition`. Sends transcript to WebSocket.
5. **AudioController** — Receives base64 WAV chunks, decodes them, queues into `AudioContext` for gapless sequential playback. Has on/off toggle.

Key implementation details for AudioController:

```typescript
// Pseudocode for audio queue
class AudioQueue {
  private ctx = new AudioContext();
  private queue: AudioBuffer[] = [];
  private playing = false;

  async addChunk(base64Wav: string) {
    const bytes = Uint8Array.from(atob(base64Wav), c => c.charCodeAt(0));
    const buffer = await this.ctx.decodeAudioData(bytes.buffer);
    this.queue.push(buffer);
    if (!this.playing) this.playNext();
  }

  private playNext() {
    if (this.queue.length === 0) { this.playing = false; return; }
    this.playing = true;
    const buffer = this.queue.shift()!;
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.ctx.destination);
    source.onended = () => this.playNext();
    source.start();
  }
}
```

Key implementation for VoiceInput:

```typescript
// Uses Web Speech API
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = new SpeechRecognition();
recognition.continuous = true;
recognition.interimResults = true;
recognition.onresult = (e) => {
  const transcript = Array.from(e.results)
    .map(r => r[0].transcript)
    .join('');
  // When final result, send to WebSocket
  if (e.results[e.results.length - 1].isFinal) {
    onSend(transcript);
  }
};
```

**Step 1: Build all components and page**

**Step 2: Test manually** — Start backend + frontend, create a course, navigate to a subtopic, verify:
- WebSocket connects
- Text input sends message and receives streaming response
- Mermaid diagrams render in right panel
- Audio plays (if TTS model loaded)
- Voice input works in Chrome

**Step 3: Commit**

```bash
git add frontend/src/pages/study/ frontend/src/components/
git commit -m "feat: conversation view with chat, diagrams, voice input, and TTS playback"
```

---

### Task 17: Quiz View

**Files:**
- Create: `frontend/src/pages/quiz/[quizId].astro`
- Create: `frontend/src/components/QuizView.tsx`

The QuizView component:
- Fetches quiz data by ID
- Renders questions one at a time or all at once
- MCQ: radio button groups
- Short answer: text input
- Diagram-based: renders Mermaid diagram + question + text input
- Submit button → calls API → shows score + feedback with explanations
- Color-coded correct/incorrect indicators

**Step 1: Build components and page**

**Step 2: Test manually**

**Step 3: Commit**

```bash
git add frontend/src/pages/quiz/ frontend/src/components/QuizView.tsx
git commit -m "feat: quiz view with MCQ, short-answer, and diagram-based questions"
```

---

## Phase 5: Integration & Polish

### Task 18: End-to-End Smoke Test

**Step 1: Start both servers**

```bash
# Terminal 1
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

**Step 2: Manual test checklist**

- [ ] Visit `http://localhost:4321` — dashboard loads
- [ ] Create a course with pasted text → sections/subtopics appear
- [ ] Create a course with PDF upload → same result
- [ ] Click into a subtopic → conversation view opens
- [ ] Type a message → AI responds with streaming text
- [ ] AI generates Mermaid diagrams proactively → diagram panel shows them
- [ ] Voice input works (Chrome) → transcript sent, AI responds
- [ ] TTS audio plays sentence-by-sentence
- [ ] Generate a quiz → quiz page loads with questions
- [ ] Submit quiz → score and feedback shown
- [ ] Progress updates reflected on course overview

**Step 3: Fix any issues found**

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Study Pal v1 — local-first STEM study companion"
```

---

## Dependency Graph

```
Task 1 (project init)
  ├── Task 2 (database) ─── Task 9 (courses API)
  ├── Task 3 (LLM client) ─┤
  ├── Task 4 (vectors) ────┤
  ├── Task 5 (TTS) ────────┤
  │                         ├── Task 6 (handout processor)
  │                         ├── Task 7 (conversation manager) ── Task 10 (WS endpoint)
  │                         └── Task 8 (quiz generator) ──────── Task 11 (quiz API)
  │
  Task 12 (Astro init)
  ├── Task 13 (API/WS clients)
  ├── Task 14 (dashboard)
  ├── Task 15 (course page)
  ├── Task 16 (conversation view) ← depends on Task 10
  └── Task 17 (quiz view) ← depends on Task 11
                                                    └── Task 18 (E2E test)
```

Backend tasks 1-11 can proceed in dependency order. Frontend tasks 12-17 can start after Task 12 and run in parallel with backend work. Task 18 needs everything complete.
