"""Async SQLite database layer for Cortex."""

import json
import uuid
from datetime import datetime, timezone

import aiosqlite

_SCHEMA = """
PRAGMA foreign_keys = ON;

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
    learning_objectives TEXT DEFAULT '[]',
    key_concepts TEXT DEFAULT '[]',
    prerequisites TEXT DEFAULT '[]',
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
    embedding BLOB,
    order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_text TEXT DEFAULT '',
    uploaded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS material_chunks (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    course_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    subtopic_id TEXT NOT NULL REFERENCES subtopics(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    diagrams TEXT DEFAULT '[]',
    sources TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS course_messages (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    diagrams TEXT DEFAULT '[]',
    sources TEXT DEFAULT '[]',
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

CREATE TABLE IF NOT EXISTS exams (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Exam Prep',
    details TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exam_resources (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_text TEXT DEFAULT '',
    uploaded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exam_resource_chunks (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL REFERENCES exam_resources(id) ON DELETE CASCADE,
    exam_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS exam_messages (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    diagrams TEXT DEFAULT '[]',
    sources TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);
"""


class Database:
    """Async SQLite database with full CRUD for Cortex."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self):
        """Open the connection and create tables."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        # Enable foreign keys (must be done per-connection, outside the schema DDL)
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        await self._migrate()

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

        # Add embedding column to chunks (for existing DBs)
        try:
            await self._db.execute("ALTER TABLE chunks ADD COLUMN embedding BLOB")
        except Exception:
            pass

        # Add sources column to messages (for existing DBs)
        try:
            await self._db.execute("ALTER TABLE messages ADD COLUMN sources TEXT DEFAULT '[]'")
        except Exception:
            pass

        # Create materials tables (for existing DBs without them)
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS materials (
                id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_text TEXT DEFAULT '',
                uploaded_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS material_chunks (
                id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                course_id TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB,
                order_index INTEGER DEFAULT 0
            );
        """)

        # Create course_messages table (for existing DBs without it)
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS course_messages (
                id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                diagrams TEXT DEFAULT '[]',
                sources TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # Create exam tables (for existing DBs without them)
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS exams (
                id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                title TEXT NOT NULL DEFAULT 'Exam Prep',
                details TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS exam_resources (
                id TEXT PRIMARY KEY,
                exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_text TEXT DEFAULT '',
                uploaded_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS exam_resource_chunks (
                id TEXT PRIMARY KEY,
                resource_id TEXT NOT NULL REFERENCES exam_resources(id) ON DELETE CASCADE,
                exam_id TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB,
                order_index INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS exam_messages (
                id TEXT PRIMARY KEY,
                exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                diagrams TEXT DEFAULT '[]',
                sources TEXT DEFAULT '[]',
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        await self._db.commit()

    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _id() -> str:
        """Generate a new UUID4 string."""
        return str(uuid.uuid4())

    # ── Helpers ──────────────────────────────────────────────────────────

    def _row_to_dict(self, row: aiosqlite.Row | None) -> dict | None:
        if row is None:
            return None
        return dict(row)

    def _rows_to_list(self, rows: list[aiosqlite.Row]) -> list[dict]:
        return [dict(r) for r in rows]

    # ── Courses ──────────────────────────────────────────────────────────

    async def create_course(
        self, name: str, description: str = "", handout_raw: str = ""
    ) -> str:
        cid = self._id()
        await self._db.execute(
            "INSERT INTO courses (id, name, description, handout_raw) VALUES (?, ?, ?, ?)",
            (cid, name, description, handout_raw),
        )
        await self._db.commit()
        return cid

    async def get_course(self, course_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM courses WHERE id = ?", (course_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row)

    async def list_courses(self) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM courses ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

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

    async def delete_course(self, course_id: str):
        await self._db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await self._db.commit()

    # ── Sections ─────────────────────────────────────────────────────────

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

    async def delete_sections_by_course(self, course_id: str):
        """Delete all sections (and cascaded subtopics/chunks) for a course."""
        await self._db.execute(
            "DELETE FROM sections WHERE course_id = ?", (course_id,)
        )
        await self._db.commit()

    async def get_sections_by_course(self, course_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM sections WHERE course_id = ? ORDER BY order_index",
            (course_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    # ── Subtopics ────────────────────────────────────────────────────────

    async def create_subtopic(
        self,
        section_id: str,
        title: str,
        content: str = "",
        summary: str = "",
        order_index: int = 0,
    ) -> str:
        sid = self._id()
        await self._db.execute(
            "INSERT INTO subtopics (id, section_id, title, content, summary, order_index) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, section_id, title, content, summary, order_index),
        )
        await self._db.commit()
        return sid

    async def get_subtopic(self, subtopic_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM subtopics WHERE id = ?", (subtopic_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row)

    async def get_subtopics_by_section(self, section_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM subtopics WHERE section_id = ? ORDER BY order_index",
            (section_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    # ── Chunks ───────────────────────────────────────────────────────────

    async def create_chunk(
        self, subtopic_id: str, content: str, order_index: int = 0
    ) -> str:
        cid = self._id()
        await self._db.execute(
            "INSERT INTO chunks (id, subtopic_id, content, order_index) VALUES (?, ?, ?, ?)",
            (cid, subtopic_id, content, order_index),
        )
        await self._db.commit()
        return cid

    async def get_chunks_by_subtopic(self, subtopic_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM chunks WHERE subtopic_id = ? ORDER BY order_index",
            (subtopic_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    async def create_chunk_with_embedding(
        self, subtopic_id: str, content: str, embedding: bytes | None = None, order_index: int = 0
    ) -> str:
        cid = self._id()
        await self._db.execute(
            "INSERT INTO chunks (id, subtopic_id, content, embedding, order_index) VALUES (?, ?, ?, ?, ?)",
            (cid, subtopic_id, content, embedding, order_index),
        )
        await self._db.commit()
        return cid

    async def update_chunk_embedding(self, chunk_id: str, embedding: bytes):
        await self._db.execute(
            "UPDATE chunks SET embedding = ? WHERE id = ?", (embedding, chunk_id)
        )
        await self._db.commit()

    async def get_chunks_with_embeddings_by_subtopic(self, subtopic_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT id, content, embedding FROM chunks WHERE subtopic_id = ? AND embedding IS NOT NULL ORDER BY order_index",
            (subtopic_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    async def get_course_id_for_subtopic(self, subtopic_id: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT s.course_id FROM subtopics st JOIN sections s ON st.section_id = s.id WHERE st.id = ?",
            (subtopic_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    # ── Materials ─────────────────────────────────────────────────────────

    async def create_material(self, course_id: str, filename: str, content_text: str = "") -> str:
        mid = self._id()
        await self._db.execute(
            "INSERT INTO materials (id, course_id, filename, content_text) VALUES (?, ?, ?, ?)",
            (mid, course_id, filename, content_text),
        )
        await self._db.commit()
        return mid

    async def get_materials_by_course(self, course_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM materials WHERE course_id = ? ORDER BY uploaded_at DESC",
            (course_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    async def delete_material(self, material_id: str):
        await self._db.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        await self._db.commit()

    async def get_material(self, material_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM materials WHERE id = ?", (material_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row)

    async def create_material_chunk(
        self, material_id: str, course_id: str, content: str, embedding: bytes | None = None, order_index: int = 0
    ) -> str:
        cid = self._id()
        await self._db.execute(
            "INSERT INTO material_chunks (id, material_id, course_id, content, embedding, order_index) VALUES (?, ?, ?, ?, ?, ?)",
            (cid, material_id, course_id, content, embedding, order_index),
        )
        await self._db.commit()
        return cid

    async def _get_material_id_for_chunk(self, chunk_id: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT material_id FROM material_chunks WHERE id = ?", (chunk_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def get_material_name_for_chunk(self, chunk_id: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT m.filename FROM material_chunks mc JOIN materials m ON mc.material_id = m.id WHERE mc.id = ?",
            (chunk_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def get_chunks_with_embeddings_by_section(self, section_id: str) -> list[dict]:
        """Get all embedded chunks for all subtopics in a section."""
        cursor = await self._db.execute(
            """SELECT c.id, c.content, c.embedding
               FROM chunks c
               JOIN subtopics st ON c.subtopic_id = st.id
               WHERE st.section_id = ? AND c.embedding IS NOT NULL
               ORDER BY st.order_index, c.order_index""",
            (section_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    async def get_material_chunks_with_embeddings_by_course(self, course_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT id, content, embedding FROM material_chunks WHERE course_id = ? AND embedding IS NOT NULL ORDER BY order_index",
            (course_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    # ── Messages ─────────────────────────────────────────────────────────

    async def save_message(
        self,
        subtopic_id: str,
        role: str,
        content: str,
        diagrams: list | None = None,
        sources: list | None = None,
    ) -> str:
        mid = self._id()
        diagrams_json = json.dumps(diagrams if diagrams is not None else [])
        sources_json = json.dumps(sources if sources is not None else [])
        await self._db.execute(
            "INSERT INTO messages (id, subtopic_id, role, content, diagrams, sources) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, subtopic_id, role, content, diagrams_json, sources_json),
        )
        await self._db.commit()
        return mid

    async def delete_messages(self, subtopic_id: str):
        """Delete all messages for a subtopic."""
        await self._db.execute(
            "DELETE FROM messages WHERE subtopic_id = ?", (subtopic_id,)
        )
        await self._db.commit()

    async def get_messages(
        self, subtopic_id: str, limit: int = 50
    ) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM messages WHERE subtopic_id = ? ORDER BY created_at ASC LIMIT ?",
            (subtopic_id, limit),
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["diagrams"] = json.loads(d["diagrams"])
            d["sources"] = json.loads(d.get("sources") or "[]")
            result.append(d)
        return result

    # ── Course Messages ─────────────────────────────────────────────────

    async def save_course_message(
        self,
        course_id: str,
        role: str,
        content: str,
        diagrams: list | None = None,
        sources: list | None = None,
    ) -> str:
        mid = self._id()
        diagrams_json = json.dumps(diagrams if diagrams is not None else [])
        sources_json = json.dumps(sources if sources is not None else [])
        await self._db.execute(
            "INSERT INTO course_messages (id, course_id, role, content, diagrams, sources) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, course_id, role, content, diagrams_json, sources_json),
        )
        await self._db.commit()
        return mid

    async def get_course_messages(self, course_id: str, limit: int = 50) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM course_messages WHERE course_id = ? ORDER BY created_at ASC LIMIT ?",
            (course_id, limit),
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["diagrams"] = json.loads(d["diagrams"])
            d["sources"] = json.loads(d.get("sources") or "[]")
            result.append(d)
        return result

    async def delete_course_messages(self, course_id: str):
        await self._db.execute(
            "DELETE FROM course_messages WHERE course_id = ?", (course_id,)
        )
        await self._db.commit()

    # ── Quizzes ──────────────────────────────────────────────────────────

    async def create_quiz(
        self,
        course_id: str,
        scope: str,
        questions: list | None = None,
        section_id: str | None = None,
        subtopic_id: str | None = None,
    ) -> str:
        qid = self._id()
        questions_json = json.dumps(questions if questions is not None else [])
        await self._db.execute(
            "INSERT INTO quizzes (id, course_id, section_id, subtopic_id, scope, questions) VALUES (?, ?, ?, ?, ?, ?)",
            (qid, course_id, section_id, subtopic_id, scope, questions_json),
        )
        await self._db.commit()
        return qid

    async def get_quiz(self, quiz_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM quizzes WHERE id = ?", (quiz_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["questions"] = json.loads(d["questions"])
        return d

    async def save_quiz_attempt(
        self, quiz_id: str, answers: list, score: float
    ) -> str:
        aid = self._id()
        answers_json = json.dumps(answers)
        await self._db.execute(
            "INSERT INTO quiz_attempts (id, quiz_id, answers, score) VALUES (?, ?, ?, ?)",
            (aid, quiz_id, answers_json, score),
        )
        await self._db.commit()
        return aid

    # ── Progress ─────────────────────────────────────────────────────────

    async def upsert_progress(self, subtopic_id: str, status: str):
        now = datetime.now(timezone.utc).isoformat()
        # Use INSERT OR REPLACE keyed on the UNIQUE subtopic_id constraint.
        # We need to preserve the id if it already exists, so we do an upsert via
        # INSERT ... ON CONFLICT.
        pid = self._id()
        await self._db.execute(
            """
            INSERT INTO progress (id, subtopic_id, status, last_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(subtopic_id) DO UPDATE SET
                status = excluded.status,
                last_active = excluded.last_active
            """,
            (pid, subtopic_id, status, now),
        )
        await self._db.commit()

    async def get_course_progress(self, course_id: str) -> list[dict]:
        cursor = await self._db.execute(
            """
            SELECT p.*, st.title AS subtopic_title, s.title AS section_title
            FROM progress p
            JOIN subtopics st ON p.subtopic_id = st.id
            JOIN sections s ON st.section_id = s.id
            WHERE s.course_id = ?
            ORDER BY s.order_index, st.order_index
            """,
            (course_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    # ── Exams ─────────────────────────────────────────────────────────────

    async def create_exam(self, course_id: str, title: str = "Exam Prep", details: str = "") -> str:
        eid = self._id()
        await self._db.execute(
            "INSERT INTO exams (id, course_id, title, details) VALUES (?, ?, ?, ?)",
            (eid, course_id, title, details),
        )
        await self._db.commit()
        return eid

    async def get_exam(self, exam_id: str) -> dict | None:
        cursor = await self._db.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
        row = await cursor.fetchone()
        return self._row_to_dict(row)

    async def get_exams_by_course(self, course_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM exams WHERE course_id = ? ORDER BY created_at DESC",
            (course_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    async def update_exam(self, exam_id: str, **fields):
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [exam_id]
        await self._db.execute(
            f"UPDATE exams SET {set_clause} WHERE id = ?", values,
        )
        await self._db.commit()

    async def delete_exam(self, exam_id: str):
        await self._db.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
        await self._db.commit()

    async def get_course_id_for_exam(self, exam_id: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT course_id FROM exams WHERE id = ?", (exam_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    # ── Exam Resources ────────────────────────────────────────────────────

    async def create_exam_resource(self, exam_id: str, filename: str, content_text: str = "") -> str:
        rid = self._id()
        await self._db.execute(
            "INSERT INTO exam_resources (id, exam_id, filename, content_text) VALUES (?, ?, ?, ?)",
            (rid, exam_id, filename, content_text),
        )
        await self._db.commit()
        return rid

    async def get_exam_resources(self, exam_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM exam_resources WHERE exam_id = ? ORDER BY uploaded_at DESC",
            (exam_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    async def get_exam_resource(self, resource_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM exam_resources WHERE id = ?", (resource_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row)

    async def delete_exam_resource(self, resource_id: str):
        await self._db.execute("DELETE FROM exam_resources WHERE id = ?", (resource_id,))
        await self._db.commit()

    async def create_exam_resource_chunk(
        self, resource_id: str, exam_id: str, content: str, embedding: bytes | None = None, order_index: int = 0
    ) -> str:
        cid = self._id()
        await self._db.execute(
            "INSERT INTO exam_resource_chunks (id, resource_id, exam_id, content, embedding, order_index) VALUES (?, ?, ?, ?, ?, ?)",
            (cid, resource_id, exam_id, content, embedding, order_index),
        )
        await self._db.commit()
        return cid

    async def get_exam_resource_chunks_with_embeddings(self, exam_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT id, content, embedding FROM exam_resource_chunks WHERE exam_id = ? AND embedding IS NOT NULL ORDER BY order_index",
            (exam_id,),
        )
        rows = await cursor.fetchall()
        return self._rows_to_list(rows)

    async def get_exam_resource_name_for_chunk(self, chunk_id: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT er.filename FROM exam_resource_chunks erc JOIN exam_resources er ON erc.resource_id = er.id WHERE erc.id = ?",
            (chunk_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def _get_exam_resource_id_for_chunk(self, chunk_id: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT resource_id FROM exam_resource_chunks WHERE id = ?", (chunk_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    # ── Exam Messages ─────────────────────────────────────────────────────

    async def save_exam_message(
        self,
        exam_id: str,
        role: str,
        content: str,
        diagrams: list | None = None,
        sources: list | None = None,
    ) -> str:
        mid = self._id()
        diagrams_json = json.dumps(diagrams if diagrams is not None else [])
        sources_json = json.dumps(sources if sources is not None else [])
        await self._db.execute(
            "INSERT INTO exam_messages (id, exam_id, role, content, diagrams, sources) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, exam_id, role, content, diagrams_json, sources_json),
        )
        await self._db.commit()
        return mid

    async def get_exam_messages(self, exam_id: str, limit: int = 50) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM exam_messages WHERE exam_id = ? ORDER BY created_at ASC LIMIT ?",
            (exam_id, limit),
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["diagrams"] = json.loads(d["diagrams"])
            d["sources"] = json.loads(d.get("sources") or "[]")
            result.append(d)
        return result

    async def delete_exam_messages(self, exam_id: str):
        await self._db.execute("DELETE FROM exam_messages WHERE exam_id = ?", (exam_id,))
        await self._db.commit()
