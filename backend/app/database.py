"""Async SQLite database layer for StudyPal."""

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
    """Async SQLite database with full CRUD for StudyPal."""

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

    # ── Messages ─────────────────────────────────────────────────────────

    async def save_message(
        self,
        subtopic_id: str,
        role: str,
        content: str,
        diagrams: list | None = None,
    ) -> str:
        mid = self._id()
        diagrams_json = json.dumps(diagrams if diagrams is not None else [])
        await self._db.execute(
            "INSERT INTO messages (id, subtopic_id, role, content, diagrams) VALUES (?, ?, ?, ?, ?)",
            (mid, subtopic_id, role, content, diagrams_json),
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
            result.append(d)
        return result

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
