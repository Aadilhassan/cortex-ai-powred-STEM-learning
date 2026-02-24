"""Conversation manager with sentence streaming and mermaid extraction."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator


def build_system_prompt(title: str, summary: str, mode: str = "chat") -> str:
    """Build a system prompt for the STEM tutor.

    Mentions the subtopic title, summary, and instructs the AI to
    proactively use Mermaid diagrams for visual explanations.
    """
    base = (
        f"You are a friendly STEM tutor having a conversation about "
        f'"{title}". {summary}\n\n'
        f"CRITICAL RULES — you MUST follow these:\n"
    )
    if mode == "live":
        base += f"- Keep replies to 2-3 short sentences. This is a live voice conversation.\n"
        base += f"- Be direct and conversational. No filler, no preamble.\n"
    else:
        base += f"- Provide clear, thorough explanations. Use worked examples when helpful.\n"
        base += f"- Be conversational but don't cut explanations short.\n"
    base += (
        f"- Use markdown formatting: **bold** for key terms, "
        f"bullet points or numbered steps when showing procedures.\n"
        f"- Use LaTeX math notation: $...$ for inline math, $$...$$ for display math.\n"
        f"- When a visual would genuinely help, add on its own line: [DIAGRAM: brief topic]\n"
        f"- Do NOT write Mermaid code yourself. Just use the [DIAGRAM: ...] signal.\n"
        f"- End with ONE question to check understanding.\n"
    )
    return base


class SentenceBuffer:
    """Accumulates streaming tokens and emits complete sentences.

    Tracks mermaid code blocks and skips them for TTS output.
    """

    # Sentence-ending punctuation followed by a space (or end of input on flush)
    _SENTENCE_END_RE = re.compile(r"([.?!])\s")

    def __init__(self) -> None:
        self.buffer: str = ""
        self.in_mermaid: bool = False
        self._mermaid_buffer: str = ""

    def feed(self, token: str) -> str | None:
        """Feed a token. Returns a complete sentence if one is detected, else None.

        Mermaid code blocks (```mermaid ... ```) are tracked but not emitted
        as sentences.
        """
        text = self.buffer + token

        # Handle mermaid block transitions
        if not self.in_mermaid:
            # Check if we're entering a mermaid block
            mermaid_start = text.find("```mermaid")
            if mermaid_start != -1:
                # Everything before the mermaid block goes to normal processing
                before = text[:mermaid_start]
                after = text[mermaid_start + len("```mermaid") :]
                self.in_mermaid = True
                self._mermaid_buffer = after

                # Try to emit a sentence from content before the mermaid block
                self.buffer = before
                return self._try_emit()

            # Normal mode: accumulate and try to emit
            self.buffer = text
            return self._try_emit()
        else:
            # Inside mermaid block: look for closing ```
            self._mermaid_buffer += token
            close_idx = self._mermaid_buffer.find("```")
            if close_idx != -1:
                # Mermaid block ended
                self.in_mermaid = False
                remaining = self._mermaid_buffer[close_idx + len("```") :]
                self._mermaid_buffer = ""
                self.buffer = remaining
                return self._try_emit()
            return None

    def _try_emit(self) -> str | None:
        """Try to extract and return a complete sentence from the buffer."""
        match = self._SENTENCE_END_RE.search(self.buffer)
        if match:
            end_pos = match.end() - 1  # include punctuation, exclude trailing space
            sentence = self.buffer[:end_pos].strip()
            self.buffer = self.buffer[match.end() :].lstrip()
            if sentence:
                # Strip diagram signals from TTS output
                cleaned = re.sub(r"\[DIAGRAM:\s*[^\]]+\]", "", sentence).strip()
                return cleaned if cleaned else None
        return None

    def flush(self) -> str | None:
        """Flush remaining buffer content."""
        text = self.buffer.strip()
        self.buffer = ""
        if text:
            cleaned = re.sub(r"\[DIAGRAM:\s*[^\]]+\]", "", text).strip()
            return cleaned if cleaned else None
        return None


# Regex to extract mermaid blocks from full response text
_MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

# Regex to detect [DIAGRAM: ...] signals in tutor response
_DIAGRAM_SIGNAL_RE = re.compile(r"\[DIAGRAM:\s*(.+?)\]")


def build_exam_system_prompt(course_name: str, exam_title: str, exam_details: str, mode: str = "chat") -> str:
    """Build a system prompt for exam prep tutoring."""
    details_block = ""
    if exam_details.strip():
        details_block = (
            f"\n\nThe student has described this exam as follows:\n"
            f'"""\n{exam_details.strip()}\n"""\n'
            f"Use this information to tailor your questions and focus areas. "
            f"Prioritize topics by their weightage and relevance to the exam pattern.\n"
        )

    base = (
        f"You are an exam preparation tutor for the course \"{course_name}\". "
        f"The student is preparing for: \"{exam_title}\".{details_block}\n"
        f"CRITICAL RULES:\n"
        f"- Practice questions conversationally. Ask one question at a time.\n"
        f"- Focus on exam-relevant topics, weightage, and patterns described by the student.\n"
        f"- When the student answers, give brief feedback (correct/incorrect + why), then move to the next question.\n"
        f"- Mix question types: conceptual, problem-solving, short-answer, based on the exam pattern.\n"
        f"- Use markdown formatting: **bold** for key terms.\n"
        f"- Use LaTeX math notation: $...$ for inline math, $$...$$ for display math.\n"
        f"- When a visual would help, add on its own line: [DIAGRAM: brief topic]\n"
        f"- Do NOT write Mermaid code yourself. Just use the [DIAGRAM: ...] signal.\n"
    )
    if mode == "live":
        base += f"- Keep responses to 2-3 short sentences. This is a live voice conversation.\n"
    else:
        base += f"- Provide thorough explanations when solving problems.\n"
    return base


class ConversationManager:
    """Manages live conversation sessions.

    Builds LLM context with system prompt + vector-retrieved chunks +
    message history, streams responses, detects sentences for TTS,
    and extracts mermaid diagrams.
    """

    def __init__(self, db, llm, embedder, vector_store, diagram_service=None) -> None:
        self.db = db
        self.llm = llm
        self.embedder = embedder
        self.vector_store = vector_store
        self.diagram_service = diagram_service

    async def get_context(
        self, subtopic_id: str, user_message: str, mode: str = "chat"
    ) -> tuple[list[dict], list[dict]]:
        """Build the full message list for the LLM.

        Returns (messages, sources) where sources is a list of
        {"name": str, "type": "subtopic"|"material"} dicts.

        1. System prompt from subtopic title/summary
        2. [CONTEXT] block with relevant chunks from vector search
           (subtopic chunks + course-wide material chunks, merged by score)
        3. Recent message history (last 10)
        4. Current user message
        """
        # 1. Get subtopic info for system prompt
        subtopic = await self.db.get_subtopic(subtopic_id)
        system_msg = {
            "role": "system",
            "content": build_system_prompt(
                subtopic["title"], subtopic.get("summary", ""), mode=mode
            ),
        }

        messages: list[dict] = [system_msg]
        sources: list[dict] = []

        # 2. Retrieve relevant chunks via vector search (or fallback to DB chunks)
        if self.embedder and self.vector_store:
            query_embedding = await self.embedder.embed(user_message)

            # Search subtopic chunks (top-3)
            subtopic_results = await self.vector_store.search(
                query_embedding, topk=3, subtopic_id=subtopic_id
            )
            # Tag source type
            for r in subtopic_results:
                r["_source_type"] = "subtopic"

            # Search course-wide material chunks (top-2)
            material_results = []
            course_id = await self.db.get_course_id_for_subtopic(subtopic_id)
            if course_id:
                material_results = await self.vector_store.search(
                    query_embedding, topk=2, course_id=course_id
                )
                for r in material_results:
                    r["_source_type"] = "material"

            # Merge by score, deduplicate, take top-5
            all_results = subtopic_results + material_results
            seen = set()
            unique = []
            for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
                if r["id"] not in seen:
                    seen.add(r["id"])
                    unique.append(r)
            top_results = unique[:5]

            if top_results:
                context_parts = [r["content"] for r in top_results]
                context_block = (
                    "[CONTEXT]\n" + "\n---\n".join(context_parts) + "\n[/CONTEXT]"
                )
                messages.append({"role": "user", "content": context_block})

                # Build source references
                seen_sources: set[str] = set()
                for r in top_results:
                    if r["_source_type"] == "subtopic":
                        key = f"subtopic:{subtopic['title']}"
                        if key not in seen_sources:
                            seen_sources.add(key)
                            sources.append({"name": subtopic["title"], "type": "subtopic"})
                    elif r["_source_type"] == "material":
                        mat_id = await self.db._get_material_id_for_chunk(r["id"])
                        mat_name = await self.db.get_material_name_for_chunk(r["id"])
                        if mat_name and mat_id:
                            key = f"material:{mat_name}"
                            if key not in seen_sources:
                                seen_sources.add(key)
                                sources.append({"name": mat_name, "type": "material", "id": mat_id})
        else:
            # Fallback: use raw chunks from DB without vector ranking
            all_chunks = await self.db.get_chunks_by_subtopic(subtopic_id)
            if all_chunks:
                context_parts = [c["content"] for c in all_chunks[:3]]
                context_block = (
                    "[CONTEXT]\n" + "\n---\n".join(context_parts) + "\n[/CONTEXT]"
                )
                messages.append({"role": "user", "content": context_block})
                sources.append({"name": subtopic["title"], "type": "subtopic"})

        # 3. Recent message history (last 10 — smaller context = faster LLM)
        history = await self.db.get_messages(subtopic_id, limit=10)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # 4. Current user message
        messages.append({"role": "user", "content": user_message})

        return messages, sources

    async def get_course_context(
        self, course_id: str, user_message: str, mode: str = "chat"
    ) -> tuple[list[dict], list[dict]]:
        """Build the full message list for a course-level chat.

        Returns (messages, sources). Searches all material chunks for the course.
        """
        course = await self.db.get_course(course_id)
        course_name = course["name"] if course else "Course"
        course_desc = course.get("description", "") if course else ""

        verbosity = (
            "- Keep replies to 2-3 short sentences. This is a live voice conversation.\n"
            "- Be direct and conversational. No filler, no preamble.\n"
            if mode == "live" else
            "- Provide clear, thorough explanations. Use worked examples when helpful.\n"
            "- Be conversational but don't cut explanations short.\n"
        )

        system_msg = {
            "role": "system",
            "content": (
                f"You are a knowledgeable STEM tutor having a conversation about the course "
                f'"{course_name}". {course_desc}\n\n'
                f"You have access to all course content across all sections and materials.\n"
                f"CRITICAL RULES:\n"
                f"{verbosity}"
                f"- Use markdown formatting: **bold** for key terms.\n"
                f"- Use LaTeX math notation: $...$ for inline math, $$...$$ for display math.\n"
                f"- When a visual would help, add on its own line: [DIAGRAM: brief topic]\n"
                f"- Do NOT write Mermaid code yourself. Just use the [DIAGRAM: ...] signal.\n"
            ),
        }

        messages: list[dict] = [system_msg]
        sources: list[dict] = []

        if self.embedder and self.vector_store:
            query_embedding = await self.embedder.embed(user_message)

            # Search course-wide material chunks (top-5)
            material_results = await self.vector_store.search(
                query_embedding, topk=5, course_id=course_id
            )
            for r in material_results:
                r["_source_type"] = "material"

            if material_results:
                context_parts = [r["content"] for r in material_results]
                context_block = (
                    "[CONTEXT]\n" + "\n---\n".join(context_parts) + "\n[/CONTEXT]"
                )
                messages.append({"role": "user", "content": context_block})

                seen_sources: set[str] = set()
                for r in material_results:
                    mat_id = await self.db._get_material_id_for_chunk(r["id"])
                    mat_name = await self.db.get_material_name_for_chunk(r["id"])
                    if mat_name and mat_id:
                        key = f"material:{mat_name}"
                        if key not in seen_sources:
                            seen_sources.add(key)
                            sources.append({"name": mat_name, "type": "material", "id": mat_id})

        # Recent message history
        history = await self.db.get_course_messages(course_id, limit=10)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})
        return messages, sources

    async def stream_course_response(
        self, course_id: str, user_message: str, mode: str = "chat"
    ) -> AsyncGenerator[tuple[str, str | list], None]:
        """Stream a response for course-level chat. Same event types as stream_response."""
        await self.db.save_course_message(course_id, "user", user_message)

        context, sources = await self.get_course_context(course_id, user_message, mode=mode)

        if sources:
            yield ("sources", sources)

        sentence_buf = SentenceBuffer()
        full_response = ""
        max_tokens = 300 if mode == "live" else 1024

        async for token in self.llm.chat_stream(context, max_tokens=max_tokens):
            full_response += token
            yield ("text_delta", token)
            sentence = sentence_buf.feed(token)
            if sentence:
                yield ("sentence", sentence)

        remaining = sentence_buf.flush()
        if remaining:
            yield ("sentence", remaining)

        diagrams = []
        if self.diagram_service:
            signals = _DIAGRAM_SIGNAL_RE.findall(full_response)
            for signal_topic in signals:
                try:
                    diagram_code = await self.diagram_service.generate(topic=signal_topic)
                    diagrams.append(diagram_code)
                    yield ("diagram", diagram_code)
                except Exception as e:
                    print(f"[conversation] Diagram generation failed: {e}")

        from app.services.diagram_service import _sanitize_mermaid
        inline_diagrams = _MERMAID_BLOCK_RE.findall(full_response)
        for diagram in inline_diagrams:
            cleaned = _sanitize_mermaid(diagram.strip())
            diagrams.append(cleaned)
            yield ("diagram", cleaned)

        await self.db.save_course_message(
            course_id, "assistant", full_response,
            diagrams=diagrams or None,
            sources=sources or None,
        )

        yield ("done", "")

    async def get_exam_context(
        self, exam_id: str, user_message: str, mode: str = "chat"
    ) -> tuple[list[dict], list[dict]]:
        """Build the full message list for an exam prep chat.

        Returns (messages, sources). Merges exam resource chunks + course material
        chunks ranked by similarity, top-5.
        """
        exam = await self.db.get_exam(exam_id)
        course_id = await self.db.get_course_id_for_exam(exam_id)
        course = await self.db.get_course(course_id) if course_id else None
        course_name = course["name"] if course else "Course"
        exam_title = exam["title"] if exam else "Exam"
        exam_details = exam.get("details", "") if exam else ""

        system_msg = {
            "role": "system",
            "content": build_exam_system_prompt(course_name, exam_title, exam_details, mode=mode),
        }

        messages: list[dict] = [system_msg]
        sources: list[dict] = []

        if self.embedder and self.vector_store:
            query_embedding = await self.embedder.embed(user_message)

            # Search exam resource chunks (top-3)
            exam_results = await self.vector_store.search(
                query_embedding, topk=3, exam_id=exam_id
            )
            for r in exam_results:
                r["_source_type"] = "exam_resource"

            # Search course-wide material chunks (top-3)
            material_results = []
            if course_id:
                material_results = await self.vector_store.search(
                    query_embedding, topk=3, course_id=course_id
                )
                for r in material_results:
                    r["_source_type"] = "material"

            # Merge by score, deduplicate, take top-5
            all_results = exam_results + material_results
            seen = set()
            unique = []
            for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
                if r["id"] not in seen:
                    seen.add(r["id"])
                    unique.append(r)
            top_results = unique[:5]

            if top_results:
                context_parts = [r["content"] for r in top_results]
                context_block = (
                    "[CONTEXT]\n" + "\n---\n".join(context_parts) + "\n[/CONTEXT]"
                )
                messages.append({"role": "user", "content": context_block})

                seen_sources: set[str] = set()
                for r in top_results:
                    if r["_source_type"] == "exam_resource":
                        res_id = await self.db._get_exam_resource_id_for_chunk(r["id"])
                        res_name = await self.db.get_exam_resource_name_for_chunk(r["id"])
                        if res_name and res_id:
                            key = f"exam_resource:{res_name}"
                            if key not in seen_sources:
                                seen_sources.add(key)
                                sources.append({"name": res_name, "type": "exam_resource", "id": res_id})
                    elif r["_source_type"] == "material":
                        mat_id = await self.db._get_material_id_for_chunk(r["id"])
                        mat_name = await self.db.get_material_name_for_chunk(r["id"])
                        if mat_name and mat_id:
                            key = f"material:{mat_name}"
                            if key not in seen_sources:
                                seen_sources.add(key)
                                sources.append({"name": mat_name, "type": "material", "id": mat_id})

        # Recent message history (last 10)
        history = await self.db.get_exam_messages(exam_id, limit=10)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})
        return messages, sources

    async def stream_exam_response(
        self, exam_id: str, user_message: str, mode: str = "chat"
    ) -> AsyncGenerator[tuple[str, str | list], None]:
        """Stream a response for exam prep chat. Same event types as stream_response."""
        await self.db.save_exam_message(exam_id, "user", user_message)

        context, sources = await self.get_exam_context(exam_id, user_message, mode=mode)

        if sources:
            yield ("sources", sources)

        sentence_buf = SentenceBuffer()
        full_response = ""
        max_tokens = 300 if mode == "live" else 1024

        async for token in self.llm.chat_stream(context, max_tokens=max_tokens):
            full_response += token
            yield ("text_delta", token)
            sentence = sentence_buf.feed(token)
            if sentence:
                yield ("sentence", sentence)

        remaining = sentence_buf.flush()
        if remaining:
            yield ("sentence", remaining)

        diagrams = []
        if self.diagram_service:
            signals = _DIAGRAM_SIGNAL_RE.findall(full_response)
            for signal_topic in signals:
                try:
                    diagram_code = await self.diagram_service.generate(topic=signal_topic)
                    diagrams.append(diagram_code)
                    yield ("diagram", diagram_code)
                except Exception as e:
                    print(f"[conversation] Diagram generation failed: {e}")

        from app.services.diagram_service import _sanitize_mermaid
        inline_diagrams = _MERMAID_BLOCK_RE.findall(full_response)
        for diagram in inline_diagrams:
            cleaned = _sanitize_mermaid(diagram.strip())
            diagrams.append(cleaned)
            yield ("diagram", cleaned)

        await self.db.save_exam_message(
            exam_id, "assistant", full_response,
            diagrams=diagrams or None,
            sources=sources or None,
        )

        yield ("done", "")

    async def stream_response(
        self, subtopic_id: str, user_message: str, mode: str = "chat"
    ) -> AsyncGenerator[tuple[str, str | list], None]:
        """Async generator yielding (type, data) tuples.

        Event types:
        - ("text_delta", token)   -- raw streaming token
        - ("sentence", text)      -- complete sentence for TTS
        - ("diagram", code)       -- extracted mermaid diagram
        - ("sources", list[dict]) -- reference sources used for this response
        - ("done", "")            -- stream complete

        Also saves user message before streaming and assistant message after.
        Updates progress to "in_progress".
        """
        # Save user message
        await self.db.save_message(subtopic_id, "user", user_message)

        # Update progress
        await self.db.upsert_progress(subtopic_id, "in_progress")

        # Build context
        context, sources = await self.get_context(subtopic_id, user_message, mode=mode)

        # Emit sources early so frontend can display them
        if sources:
            yield ("sources", sources)

        # Stream response from LLM
        sentence_buf = SentenceBuffer()
        full_response = ""
        max_tokens = 250 if mode == "live" else 1024

        async for token in self.llm.chat_stream(context, max_tokens=max_tokens):
            full_response += token
            yield ("text_delta", token)

            # Try to detect a complete sentence
            sentence = sentence_buf.feed(token)
            if sentence:
                yield ("sentence", sentence)

        # Flush any remaining sentence
        remaining = sentence_buf.flush()
        if remaining:
            yield ("sentence", remaining)

        # Detect diagram signals and generate via diagram service
        diagrams = []
        if self.diagram_service:
            signals = _DIAGRAM_SIGNAL_RE.findall(full_response)
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
                    import traceback
                    print(f"[conversation] Diagram generation failed: {e}")
                    traceback.print_exc()

        # Also extract any inline mermaid blocks (fallback) — sanitize them
        from app.services.diagram_service import _sanitize_mermaid

        inline_diagrams = _MERMAID_BLOCK_RE.findall(full_response)
        for diagram in inline_diagrams:
            cleaned = _sanitize_mermaid(diagram.strip())
            diagrams.append(cleaned)
            yield ("diagram", cleaned)

        # Save assistant message with diagrams and sources
        await self.db.save_message(
            subtopic_id, "assistant", full_response,
            diagrams=diagrams or None,
            sources=sources or None,
        )

        yield ("done", "")
