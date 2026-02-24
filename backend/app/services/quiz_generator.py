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
        """Gather text content based on scope.

        - "subtopic": get chunks for that subtopic
        - "topic": get chunks for all subtopics in that section
        - "course": get chunks for all sections in that course
        """
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

    async def generate(
        self,
        course_id: str,
        scope: str,
        num_questions: int = 5,
        section_id: str | None = None,
        subtopic_id: str | None = None,
    ) -> str:
        """Generate a quiz. Returns quiz_id."""
        content = await self._gather_content(
            scope=scope,
            course_id=course_id,
            section_id=section_id,
            subtopic_id=subtopic_id,
        )

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

    async def score(
        self, questions: list[dict], answers: list
    ) -> tuple[float, list[dict]]:
        """Score answers against questions.

        Returns (percentage, feedback_list).
        - MCQ: exact match
        - short_answer: case-insensitive match
        - diagram: case-insensitive match
        """
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
                # short_answer and diagram: case-insensitive
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
