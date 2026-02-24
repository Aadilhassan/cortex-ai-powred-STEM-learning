# OpenRouter Multi-Model Migration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate study-pal from Groq to OpenRouter with MiniMax M2.5 for primary LLM tasks and Codestral for diagram generation. Simplify course creation so user only uploads a handout and the LLM extracts name, description, and a rich course structure.

**Architecture:** Two `LLMClient` instances (primary + diagram) pointing at OpenRouter with different models. New `DiagramService` wraps the diagram client. Handout processor enhanced to auto-extract course metadata. STT stays on Groq.

**Tech Stack:** FastAPI, httpx (LLM client), OpenRouter API (OpenAI-compatible), aiosqlite, React/TypeScript frontend

---

### Task 1: Update config.py — OpenRouter credentials and model IDs

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Edit config.py**

Replace the Groq-specific config with OpenRouter config. Keep `GROQ_API_KEY` for STT only.

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

# OpenRouter (primary LLM provider)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PRIMARY_MODEL = "minimax/minimax-m2.5"
DIAGRAM_MODEL = "mistralai/codestral-2501"

# Groq (STT only)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
```

**Step 2: Update .env file**

Ensure `.env` has `OPENROUTER_API_KEY` set. The `GROQ_API_KEY` remains for STT.

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: switch config from Groq to OpenRouter with dual model setup"
```

---

### Task 2: Update llm_client.py — Remove Groq defaults

**Files:**
- Modify: `backend/app/services/llm_client.py`

**Step 1: Update the default base URL and model**

Change `DEFAULT_BASE_URL` to OpenRouter and update default model parameter. The class already supports any OpenAI-compatible API, so only defaults need changing.

```python
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
```

And update the `__init__` signature:

```python
def __init__(self, api_key: str, model: str = "minimax/minimax-m2.5", base_url: str = DEFAULT_BASE_URL) -> None:
```

No other changes needed — the class is already generic.

**Step 2: Commit**

```bash
git add backend/app/services/llm_client.py
git commit -m "feat: update LLMClient defaults to OpenRouter"
```

---

### Task 3: Update database.py — Add rich section columns

**Files:**
- Modify: `backend/app/database.py`

**Step 1: Add columns to the sections table schema**

Add `learning_objectives`, `key_concepts`, `prerequisites` columns (all TEXT storing JSON arrays) to the `sections` CREATE TABLE statement.

In the `_SCHEMA` string, change the `sections` table to:

```sql
CREATE TABLE IF NOT EXISTS sections (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    learning_objectives TEXT DEFAULT '[]',
    key_concepts TEXT DEFAULT '[]',
    prerequisites TEXT DEFAULT '[]',
    order_index INTEGER DEFAULT 0
);
```

**Step 2: Update create_section to accept new fields**

```python
async def create_section(
    self,
    course_id: str,
    title: str,
    summary: str = "",
    order_index: int = 0,
    learning_objectives: list | None = None,
    key_concepts: list | None = None,
    prerequisites: list | None = None,
) -> str:
    sid = self._id()
    await self._db.execute(
        "INSERT INTO sections (id, course_id, title, summary, learning_objectives, key_concepts, prerequisites, order_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            sid,
            course_id,
            title,
            summary,
            json.dumps(learning_objectives or []),
            json.dumps(key_concepts or []),
            json.dumps(prerequisites or []),
            order_index,
        ),
    )
    await self._db.commit()
    return sid
```

**Step 3: Add a migration method to the Database class**

Add a method called during `initialize()` to add columns to existing DBs:

```python
async def _migrate(self):
    """Add columns that may be missing from older schemas."""
    for col, default in [
        ("learning_objectives", "'[]'"),
        ("key_concepts", "'[]'"),
        ("prerequisites", "'[]'"),
    ]:
        try:
            await self._db.execute(
                f"ALTER TABLE sections ADD COLUMN {col} TEXT DEFAULT {default}"
            )
        except Exception:
            pass  # Column already exists
    await self._db.commit()
```

Call `await self._migrate()` at the end of `initialize()`.

**Step 4: Commit**

```bash
git add backend/app/database.py
git commit -m "feat: add learning_objectives, key_concepts, prerequisites to sections table"
```

---

### Task 4: Update handout_processor.py — Enhanced LLM prompt with auto-extraction

**Files:**
- Modify: `backend/app/services/handout_processor.py`

**Step 1: Replace PARSE_PROMPT with enhanced version**

The new prompt asks the LLM to extract course name, description, and richer section structure:

```python
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
```

**Step 2: Update the process method to return extracted metadata and handle new structure**

```python
async def process(self, course_id: str, text: str) -> dict:
    """Parse handout text into sections/subtopics, chunk, embed, and index.

    Returns dict with extracted 'name' and 'description'.
    """
    result = await self.llm.chat_json(
        [{"role": "user", "content": PARSE_PROMPT + text}]
    )

    # Extract course metadata
    extracted = {
        "name": result.get("name", "Untitled Course"),
        "description": result.get("description", ""),
    }

    sections = result.get("sections", [])

    for sec_idx, section in enumerate(sections):
        section_id = await self.db.create_section(
            course_id,
            section["title"],
            section.get("summary", ""),
            sec_idx,
            learning_objectives=section.get("learning_objectives"),
            key_concepts=section.get("key_concepts"),
            prerequisites=section.get("prerequisites"),
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

            for i, chunk_text_val in enumerate(chunks):
                await self.db.create_chunk(subtopic_id, chunk_text_val, i)

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

    return extracted
```

**Step 3: Commit**

```bash
git add backend/app/services/handout_processor.py
git commit -m "feat: enhanced handout processor with auto-extraction of name, description, and rich section metadata"
```

---

### Task 5: Update courses.py — Simplified course creation endpoints

**Files:**
- Modify: `backend/app/routers/courses.py`

**Step 1: Update CourseCreate model — make name optional**

```python
class CourseCreate(BaseModel):
    handout_text: str
```

**Step 2: Rewrite create_course endpoint**

```python
@router.post("/courses")
async def create_course(body: CourseCreate, request: Request):
    """Create a course from handout text. Name and description are auto-extracted by the LLM."""
    db = _get_db(request)
    processor = _get_processor(request)

    if not body.handout_text.strip():
        raise HTTPException(status_code=400, detail="Handout text is required")

    # Create course with placeholder name (will be updated after processing)
    course_id = await db.create_course(
        name="Processing...",
        description="",
        handout_raw=body.handout_text,
    )

    try:
        extracted = await processor.process(course_id, body.handout_text)
        # Update course with LLM-extracted name and description
        await db.update_course(course_id, name=extracted["name"], description=extracted["description"])
    except Exception as e:
        print(f"[courses] Handout processing failed: {e}")
        await db.update_course(course_id, name="Untitled Course")

    course = await db.get_course(course_id)
    return course
```

**Step 3: Rewrite create_course_upload endpoint**

```python
@router.post("/courses/upload")
async def create_course_upload(
    request: Request,
    file: UploadFile = File(...),
):
    """Create a course from a file upload (PDF or text). Name and description are auto-extracted."""
    db = _get_db(request)
    processor = _get_processor(request)

    file_bytes = await file.read()

    if file.filename and file.filename.lower().endswith(".pdf"):
        handout_text = extract_text_from_pdf(file_bytes)
    else:
        handout_text = file_bytes.decode("utf-8")

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
```

**Step 4: Add update_course method to database.py**

In `backend/app/database.py`, add:

```python
async def update_course(self, course_id: str, **fields):
    """Update specific fields on a course."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [course_id]
    await self._db.execute(
        f"UPDATE courses SET {set_clause} WHERE id = ?",
        values,
    )
    await self._db.commit()
```

**Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/app/database.py
git commit -m "feat: simplified course creation — auto-extract name/description from handout"
```

---

### Task 6: Create diagram_service.py — Dedicated diagram generation

**Files:**
- Create: `backend/app/services/diagram_service.py`

**Step 1: Create the diagram service**

```python
"""Diagram generation service using a dedicated code-focused LLM."""

from __future__ import annotations


_DIAGRAM_PROMPT = """You are a diagram generator. Generate a Mermaid diagram for the given topic.

Rules:
- Output ONLY the Mermaid code (no markdown fences, no explanation)
- Use simple labels without special characters
- Do not use parentheses inside [] node labels
- Do not include style, classDef, or class lines
- Make diagrams clear and focused

{type_hint}
Topic: {topic}
{context_block}"""


class DiagramService:
    """Generate Mermaid diagrams using a dedicated LLM."""

    def __init__(self, llm):
        self.llm = llm

    async def generate(
        self,
        topic: str,
        context: str | None = None,
        diagram_type: str | None = None,
    ) -> str:
        """Generate a Mermaid diagram for the given topic."""
        type_hint = ""
        if diagram_type:
            type_hint = f"Diagram type: {diagram_type}"

        context_block = ""
        if context:
            context_block = f"Context:\n{context}"

        prompt = _DIAGRAM_PROMPT.format(
            topic=topic,
            type_hint=type_hint,
            context_block=context_block,
        )

        result = await self.llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        # Strip any accidental markdown fences
        code = result.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            # Remove first and last lines (fences)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines)

        return code.strip()
```

**Step 2: Commit**

```bash
git add backend/app/services/diagram_service.py
git commit -m "feat: add DiagramService for dedicated Mermaid diagram generation via Codestral"
```

---

### Task 7: Create diagrams router — REST endpoint for on-demand diagrams

**Files:**
- Create: `backend/app/routers/diagrams.py`

**Step 1: Create the router**

```python
"""On-demand diagram generation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["diagrams"])


class DiagramRequest(BaseModel):
    topic: str
    context: str | None = None
    diagram_type: str | None = None


@router.post("/diagrams")
async def generate_diagram(body: DiagramRequest, request: Request):
    """Generate a Mermaid diagram for a given topic."""
    diagram_service = request.app.state.diagram_service
    mermaid_code = await diagram_service.generate(
        topic=body.topic,
        context=body.context,
        diagram_type=body.diagram_type,
    )
    return {"mermaid": mermaid_code}
```

**Step 2: Commit**

```bash
git add backend/app/routers/diagrams.py
git commit -m "feat: add POST /api/diagrams endpoint for on-demand diagram generation"
```

---

### Task 8: Update conversation.py — Delegate diagram generation to DiagramService

**Files:**
- Modify: `backend/app/services/conversation.py`

**Step 1: Update the system prompt to use diagram signals**

Replace the Mermaid instructions in `build_system_prompt` so the tutor emits a signal instead of raw Mermaid:

```python
def build_system_prompt(title: str, summary: str) -> str:
    return (
        f"You are a friendly STEM tutor having a real-time voice conversation about "
        f'"{title}". {summary}\n\n'
        f"CRITICAL RULES:\n"
        f"- Keep responses SHORT (2-4 sentences max). This is a live conversation, not a lecture.\n"
        f"- Talk naturally like a tutor sitting next to the student. Be direct.\n"
        f"- Only elaborate when the student asks for more detail.\n"
        f"- When a visual diagram would genuinely help, include a signal on its own line: [DIAGRAM: brief description of what to visualize]\n"
        f"- Do NOT write Mermaid code yourself. Just use the [DIAGRAM: ...] signal.\n"
        f"- Ask the student questions back to check understanding.\n"
        f"- Never dump walls of text. If a topic is complex, break it across conversation turns.\n"
    )
```

**Step 2: Update ConversationManager to accept a diagram_service**

```python
class ConversationManager:
    def __init__(self, db, llm, embedder, vector_store, diagram_service=None) -> None:
        self.db = db
        self.llm = llm
        self.embedder = embedder
        self.vector_store = vector_store
        self.diagram_service = diagram_service
```

**Step 3: Update stream_response to detect [DIAGRAM: ...] signals and delegate**

Add a regex at the module level:

```python
_DIAGRAM_SIGNAL_RE = re.compile(r"\[DIAGRAM:\s*(.+?)\]")
```

Update `stream_response` — after streaming completes, detect diagram signals and generate diagrams via the diagram service. Remove the old `_MERMAID_BLOCK_RE` extraction:

```python
async def stream_response(
    self, subtopic_id: str, user_message: str
) -> AsyncGenerator[tuple[str, str], None]:
    # Save user message
    await self.db.save_message(subtopic_id, "user", user_message)
    await self.db.upsert_progress(subtopic_id, "in_progress")

    context = await self.get_context(subtopic_id, user_message)

    sentence_buf = SentenceBuffer()
    full_response = ""

    async for token in self.llm.chat_stream(context):
        full_response += token
        yield ("text_delta", token)

        sentence = sentence_buf.feed(token)
        if sentence:
            yield ("sentence", sentence)

    remaining = sentence_buf.flush()
    if remaining:
        yield ("sentence", remaining)

    # Detect diagram signals and generate via diagram service
    diagrams = []
    if self.diagram_service:
        signals = _DIAGRAM_SIGNAL_RE.findall(full_response)
        # Get subtopic context for better diagram generation
        subtopic = await self.db.get_subtopic(subtopic_id)
        subtopic_context = subtopic.get("summary", "") if subtopic else ""

        for signal_topic in signals:
            try:
                diagram_code = await self.diagram_service.generate(
                    topic=signal_topic,
                    context=subtopic_context,
                )
                diagrams.append(diagram_code)
                yield ("diagram", diagram_code)
            except Exception as e:
                print(f"[conversation] Diagram generation failed: {e}")

    # Also extract any inline mermaid blocks (fallback)
    inline_diagrams = _MERMAID_BLOCK_RE.findall(full_response)
    for diagram in inline_diagrams:
        stripped = diagram.strip()
        diagrams.append(stripped)
        yield ("diagram", stripped)

    await self.db.save_message(
        subtopic_id, "assistant", full_response, diagrams=diagrams or None
    )

    yield ("done", "")
```

**Step 4: Update SentenceBuffer to also skip [DIAGRAM: ...] signals from TTS**

In the `feed` method, add detection for diagram signals similar to mermaid block detection. The simplest approach: treat `[DIAGRAM:` as a marker that gets included in text but is skipped by TTS. Since it's a short inline signal (not a multi-line block), no changes are needed — the sentence buffer will pass it through as text, which is fine. The signal is short enough that TTS reading it is acceptable, but we should strip it for cleaner TTS:

In `_try_emit`, filter out diagram signals from emitted sentences:

```python
def _try_emit(self) -> str | None:
    match = self._SENTENCE_END_RE.search(self.buffer)
    if match:
        end_pos = match.end() - 1
        sentence = self.buffer[:end_pos].strip()
        self.buffer = self.buffer[match.end():].lstrip()
        if sentence:
            # Strip diagram signals from TTS output
            cleaned = re.sub(r"\[DIAGRAM:\s*[^\]]+\]", "", sentence).strip()
            return cleaned if cleaned else None
    return None
```

Also update `flush`:

```python
def flush(self) -> str | None:
    text = self.buffer.strip()
    self.buffer = ""
    if text:
        cleaned = re.sub(r"\[DIAGRAM:\s*[^\]]+\]", "", text).strip()
        return cleaned if cleaned else None
    return None
```

**Step 5: Commit**

```bash
git add backend/app/services/conversation.py
git commit -m "feat: delegate diagram generation to DiagramService via [DIAGRAM:] signals"
```

---

### Task 9: Update main.py — Wire up dual LLM clients and new services

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Update imports and lifespan to create two LLM clients**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import (
        DATA_DIR,
        DB_PATH,
        OPENROUTER_API_KEY,
        OPENROUTER_BASE_URL,
        PRIMARY_MODEL,
        DIAGRAM_MODEL,
        GROQ_API_KEY,
        VECTOR_DIR,
    )
    from app.database import Database
    from app.services.llm_client import LLMClient

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    print("[startup] Initializing database...")
    db = Database(str(DB_PATH))
    await db.initialize()
    print("[startup] Database ready")

    primary_llm = LLMClient(api_key=OPENROUTER_API_KEY, model=PRIMARY_MODEL, base_url=OPENROUTER_BASE_URL)
    print(f"[startup] Primary LLM ready ({PRIMARY_MODEL})")

    diagram_llm = LLMClient(api_key=OPENROUTER_API_KEY, model=DIAGRAM_MODEL, base_url=OPENROUTER_BASE_URL)
    print(f"[startup] Diagram LLM ready ({DIAGRAM_MODEL})")

    # Embedder
    embedder = None
    try:
        from app.services.embedder import Embedder
        embedder = Embedder()
        print("[startup] Embedder ready")
    except Exception as e:
        print(f"[startup] Embedder failed: {e}")

    # Vector store
    vector_store = None
    if _can_import("zvec"):
        try:
            from app.services.vector_store import VectorStore
            vector_store = VectorStore(VECTOR_DIR)
            print("[startup] Vector store ready")
        except Exception as e:
            print(f"[startup] Vector store failed: {e}")
    else:
        print("[startup] Vector store skipped (zvec not compatible with this CPU)")

    # TTS
    tts = None
    if not os.getenv("TESTING"):
        try:
            from app.services.tts_engine import TTSEngine
            tts = TTSEngine(voice="Kiki")
            print("[startup] TTS ready (KittenTTS nano - Kiki)")
        except Exception as e:
            print(f"[startup] TTS failed: {e}")

    # STT (still uses Groq)
    stt = None
    if not os.getenv("TESTING"):
        try:
            from app.services.stt_engine import STTEngine
            stt = STTEngine(api_key=GROQ_API_KEY)
            print("[startup] STT ready (Groq Whisper)")
        except Exception as e:
            print(f"[startup] STT failed: {e}")

    # Wire up services
    from app.services.conversation import ConversationManager
    from app.services.diagram_service import DiagramService
    from app.services.handout_processor import HandoutProcessor
    from app.services.quiz_generator import QuizGenerator

    diagram_service = DiagramService(diagram_llm)

    app.state.db = db
    app.state.primary_llm = primary_llm
    app.state.diagram_llm = diagram_llm
    app.state.embedder = embedder
    app.state.vector_store = vector_store
    app.state.tts = tts
    app.state.stt = stt
    app.state.diagram_service = diagram_service
    app.state.handout_processor = HandoutProcessor(db, primary_llm, embedder, vector_store)
    app.state.conversation = ConversationManager(db, primary_llm, embedder, vector_store, diagram_service)
    app.state.quiz_generator = QuizGenerator(db, primary_llm)

    print("[startup] All services initialized!")

    yield

    await primary_llm.close()
    await diagram_llm.close()
    await db.close()
```

**Step 2: Register the diagrams router**

Add the import and include:

```python
from app.routers import chat, courses, diagrams, progress, quiz

app.include_router(diagrams.router, prefix="/api")
```

**Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: wire up dual LLM clients (primary + diagram) and diagram service"
```

---

### Task 10: Update frontend — Simplified course creation modal

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/Dashboard.tsx`

**Step 1: Update api.ts — Simplify createCourse and uploadCourse**

```typescript
export async function createCourse(handoutText: string) {
  const r = await fetch(`${BASE}/courses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ handout_text: handoutText }),
  });
  return r.json();
}

export async function uploadCourse(file: File) {
  const form = new FormData();
  form.append('file', file);
  const r = await fetch(`${BASE}/courses/upload`, { method: 'POST', body: form });
  return r.json();
}
```

**Step 2: Update Dashboard.tsx — Remove name/description fields from CreateCourseModal**

Remove the `name` and `description` state variables and input fields. Remove the validation that requires a name. Update `handleCreate`:

```typescript
function CreateCourseModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (course: Course) => void;
}) {
  const [tab, setTab] = useState<'paste' | 'upload'>('paste');
  const [handoutText, setHandoutText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleCreate() {
    if (tab === 'paste' && !handoutText.trim()) {
      setError('Please paste your handout text.');
      return;
    }
    if (tab === 'upload' && !file) {
      setError('Please select a file to upload.');
      return;
    }

    setCreating(true);
    setError('');

    try {
      let course: Course;
      if (tab === 'upload' && file) {
        course = await uploadCourse(file);
      } else {
        course = await createCourse(handoutText);
      }
      onCreated(course);
    } catch (e) {
      console.error('Failed to create course', e);
      setError('Failed to create course. Please try again.');
    } finally {
      setCreating(false);
    }
  }

  // ... rest of the modal remains the same but WITHOUT the name and description inputs
  // Remove the "Course Name" label + input
  // Remove the "Description" label + textarea
  // The modal starts directly with the tab toggle (paste/upload)
```

The modal title should change to "Create Course from Handout" and the create button text should say "Create Course" (or "Analyzing..." while creating).

**Step 3: Update button text for loading state**

```typescript
{creating ? 'Analyzing handout...' : 'Create Course'}
```

**Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/Dashboard.tsx
git commit -m "feat: simplified course creation UI — just upload/paste handout"
```

---

### Task 11: Add diagram generation button to StudyView

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/StudyView.tsx`

**Step 1: Add generateDiagram API function**

In `frontend/src/lib/api.ts`, add:

```typescript
export async function generateDiagram(topic: string, context?: string, diagramType?: string) {
  const r = await fetch(`${BASE}/diagrams`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, context, diagram_type: diagramType }),
  });
  return r.json();
}
```

**Step 2: Add a "Generate Diagram" button to the header in StudyView**

Import the new API function and add a button in the header alongside the existing buttons. When clicked, prompt for a topic and call the API:

In the header `div` with existing buttons, add:

```tsx
<button
  onClick={async () => {
    const topic = prompt('What should the diagram show?');
    if (!topic) return;
    try {
      const { mermaid: code } = await generateDiagram(topic);
      if (code) {
        setDiagrams(prev => [...prev, code]);
        setIsDiagramOpen(true);
      }
    } catch (e) {
      console.error('Diagram generation failed', e);
    }
  }}
  style={styles.clearChatBtn}
  title="Generate a diagram on any topic"
>
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M3 9h18M9 21V9" />
  </svg>
  Diagram
</button>
```

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/StudyView.tsx
git commit -m "feat: add on-demand diagram generation button to study view"
```

---

### Task 12: Final integration test

**Step 1: Start the backend**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
```

Verify startup logs show:
- `[startup] Primary LLM ready (minimax/minimax-m2.5)`
- `[startup] Diagram LLM ready (mistralai/codestral-2501)`

**Step 2: Test course creation**

```bash
curl -X POST http://localhost:8000/api/courses \
  -H "Content-Type: application/json" \
  -d '{"handout_text": "This is a course about linear algebra. Topics include vectors, matrices, and eigenvalues."}'
```

Verify the response includes an auto-extracted `name` and `description`.

**Step 3: Test diagram endpoint**

```bash
curl -X POST http://localhost:8000/api/diagrams \
  -H "Content-Type: application/json" \
  -d '{"topic": "How HTTP request-response cycle works"}'
```

Verify the response includes valid Mermaid code.

**Step 4: Commit final state if any fixes were needed**

```bash
git add -A
git commit -m "fix: integration fixes for OpenRouter multi-model setup"
```
