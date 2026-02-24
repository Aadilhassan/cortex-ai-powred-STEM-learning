"""Quiz generator: creates quizzes from course content at different scopes."""

from __future__ import annotations

_QUIZ_PROMPT_TEMPLATE = """\
You are a quiz generator. Based on the following study material, generate exactly {num_questions} quiz questions.

Mix the question types among: mcq, short_answer, and diagram.

Return ONLY a JSON array (no markdown fences) in this exact format:
[
  {{"type": "mcq", "question": "...", "options": ["A","B","C","D"], "correct_answer": "A", "explanation": "..."}},
  {{"type": "short_answer", "question": "...", "correct_answer": "...", "explanation": "..."}},
  {{"type": "diagram", "question": "...", "diagram": "graph TD\\nA-->B", "correct_answer": "...", "explanation": "..."}}
]

Study material:
{content}
"""

_EXAM_PROMPT_TEMPLATE = """\
You are a university exam paper generator. Create a {exam_type_label} exam with exactly {num_questions} questions.

{exam_instructions}

Question type distribution:
- ~50% MCQ (multiple choice, 4 options each)
- ~30% short_answer (require a 1-3 sentence answer)
- ~20% diagram (include a mermaid diagram and ask about it)

Difficulty: Mix easy (30%), medium (50%), and hard (20%) questions.
Mark each question with a "difficulty" field: "easy", "medium", or "hard".

Return ONLY a JSON array (no markdown fences) in this exact format:
[
  {{"type": "mcq", "question": "...", "options": ["A","B","C","D"], "correct_answer": "A", "explanation": "...", "difficulty": "medium"}},
  {{"type": "short_answer", "question": "...", "correct_answer": "...", "explanation": "...", "difficulty": "easy"}},
  {{"type": "diagram", "question": "...", "diagram": "graph TD\\nA-->B", "correct_answer": "...", "explanation": "...", "difficulty": "hard"}}
]

Study material:
{content}
"""

_EXAM_CONFIGS = {
    "midterm": {
        "label": "Midterm",
        "default_questions": 15,
        "instructions": (
            "This is a MIDTERM exam covering the first half of the course material.\n"
            "Focus on foundational concepts, definitions, and core understanding.\n"
            "Questions should test recall and basic application of concepts."
        ),
    },
    "comprehensive": {
        "label": "Comprehensive Final",
        "default_questions": 25,
        "instructions": (
            "This is a COMPREHENSIVE FINAL exam covering ALL course material.\n"
            "Include questions that test deep understanding, connections between topics, "
            "and ability to apply concepts to new scenarios.\n"
            "Questions should range from recall to analysis and synthesis."
        ),
    },
}


class QuizGenerator:
    """Generates quizzes from course content and scores answers."""

    def __init__(self, db, llm):
        self.db = db
        self.llm = llm

    async def _gather_content(
        self,
        scope: str,
        course_id: str | None = None,
        section_id: str | None = None,
        subtopic_id: str | None = None,
    ) -> str:
        """Gather text content based on scope."""
        chunks_text: list[str] = []

        if scope == "subtopic":
            chunks = await self.db.get_chunks_by_subtopic(subtopic_id)
            chunks_text = [c["content"] for c in chunks]

        elif scope == "topic":
            subtopics = await self.db.get_subtopics_by_section(section_id)
            for st in subtopics:
                chunks = await self.db.get_chunks_by_subtopic(st["id"])
                chunks_text.extend(c["content"] for c in chunks)

        elif scope == "course":
            sections = await self.db.get_sections_by_course(course_id)
            for sec in sections:
                subtopics = await self.db.get_subtopics_by_section(sec["id"])
                for st in subtopics:
                    chunks = await self.db.get_chunks_by_subtopic(st["id"])
                    chunks_text.extend(c["content"] for c in chunks)

        return "\n\n".join(chunks_text)

    async def _gather_exam_content(
        self,
        course_id: str,
        exam_type: str,
    ) -> str:
        """Gather content for an exam. For midterm, use first half of sections."""
        sections = await self.db.get_sections_by_course(course_id)

        if exam_type == "midterm":
            # First half of sections
            half = max(1, len(sections) // 2)
            sections = sections[:half]

        chunks_text: list[str] = []
        for sec in sections:
            subtopics = await self.db.get_subtopics_by_section(sec["id"])
            for st in subtopics:
                chunks = await self.db.get_chunks_by_subtopic(st["id"])
                chunks_text.extend(c["content"] for c in chunks)

        # Also include material content
        all_materials = await self.db.get_materials_by_course(course_id)
        for m in all_materials:
            full_m = await self.db.get_material(m["id"])
            if full_m and full_m.get("content_text", "").strip():
                chunks_text.append(full_m["content_text"][:2000])

        return "\n\n".join(chunks_text)

    async def generate(
        self,
        course_id: str,
        scope: str,
        num_questions: int = 5,
        section_id: str | None = None,
        subtopic_id: str | None = None,
        exam_type: str | None = None,
    ) -> str:
        """Generate a quiz or exam. Returns quiz_id."""
        if exam_type and exam_type in _EXAM_CONFIGS:
            # Use exam-specific default question count (ignore the generic default of 5)
            exam_n = num_questions if num_questions != 5 else None
            return await self._generate_exam(course_id, exam_type, exam_n)

        content = await self._gather_content(
            scope=scope,
            course_id=course_id,
            section_id=section_id,
            subtopic_id=subtopic_id,
        )

        if not content.strip():
            course = await self.db.get_course(course_id)
            content = course.get("handout_raw", "") if course else ""

        if not content.strip():
            raise ValueError("No content available to generate quiz from.")

        prompt = _QUIZ_PROMPT_TEMPLATE.format(
            num_questions=num_questions,
            content=content,
        )

        messages = [{"role": "user", "content": prompt}]
        questions = await self.llm.chat_json(messages)

        quiz_id = await self.db.create_quiz(
            course_id=course_id,
            scope=scope,
            questions=questions,
            section_id=section_id,
            subtopic_id=subtopic_id,
        )

        return quiz_id

    async def _generate_exam(
        self,
        course_id: str,
        exam_type: str,
        num_questions: int | None = None,
    ) -> str:
        """Generate an exam (midterm or comprehensive)."""
        config = _EXAM_CONFIGS[exam_type]
        n = num_questions if num_questions and num_questions > 0 else config["default_questions"]

        content = await self._gather_exam_content(course_id, exam_type)

        if not content.strip():
            course = await self.db.get_course(course_id)
            content = course.get("handout_raw", "") if course else ""

        if not content.strip():
            raise ValueError("No content available to generate exam from.")

        prompt = _EXAM_PROMPT_TEMPLATE.format(
            exam_type_label=config["label"],
            num_questions=n,
            exam_instructions=config["instructions"],
            content=content,
        )

        messages = [{"role": "user", "content": prompt}]
        questions = await self.llm.chat_json(messages)

        quiz_id = await self.db.create_quiz(
            course_id=course_id,
            scope=f"exam_{exam_type}",
            questions=questions,
        )

        return quiz_id

    async def score(
        self, questions: list[dict], answers: list
    ) -> tuple[float, list[dict]]:
        """Score answers against questions."""
        if not questions:
            return 0.0, []

        feedback: list[dict] = []
        correct_count = 0

        for question, answer in zip(questions, answers):
            q_type = question["type"]
            expected = question["correct_answer"]

            if q_type == "mcq":
                is_correct = answer == expected
            else:
                is_correct = str(answer).lower() == str(expected).lower()

            if is_correct:
                correct_count += 1

            feedback.append(
                {
                    "question": question["question"],
                    "your_answer": answer,
                    "correct_answer": expected,
                    "correct": is_correct,
                    "explanation": question.get("explanation", ""),
                }
            )

        percentage = (correct_count / len(questions)) * 100
        return percentage, feedback
