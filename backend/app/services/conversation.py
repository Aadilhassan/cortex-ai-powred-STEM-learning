"""Conversation manager with sentence streaming and mermaid extraction."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator


def build_system_prompt(title: str, summary: str) -> str:
    """Build a system prompt for the STEM tutor.

    Mentions the subtopic title, summary, and instructs the AI to
    proactively use Mermaid diagrams for visual explanations.
    """
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

    async def get_context(self, subtopic_id: str, user_message: str) -> list[dict]:
        """Build the full message list for the LLM.

        1. System prompt from subtopic title/summary
        2. [CONTEXT] block with relevant chunks from vector search
        3. Recent message history (last 20)
        4. Current user message
        """
        # 1. Get subtopic info for system prompt
        subtopic = await self.db.get_subtopic(subtopic_id)
        system_msg = {
            "role": "system",
            "content": build_system_prompt(
                subtopic["title"], subtopic.get("summary", "")
            ),
        }

        messages: list[dict] = [system_msg]

        # 2. Retrieve relevant chunks via vector search (or fallback to DB chunks)
        if self.embedder and self.vector_store:
            query_embedding = self.embedder.embed(user_message)
            search_results = self.vector_store.search(
                query_embedding, topk=5, subtopic_id=subtopic_id
            )

            if search_results:
                all_chunks = await self.db.get_chunks_by_subtopic(subtopic_id)
                chunk_map = {c["id"]: c["content"] for c in all_chunks}

                context_parts = []
                for result in search_results:
                    chunk_content = chunk_map.get(result["id"])
                    if chunk_content:
                        context_parts.append(chunk_content)

                if context_parts:
                    context_block = (
                        "[CONTEXT]\n" + "\n---\n".join(context_parts) + "\n[/CONTEXT]"
                    )
                    messages.append({"role": "user", "content": context_block})
        else:
            # Fallback: use raw chunks from DB without vector ranking
            all_chunks = await self.db.get_chunks_by_subtopic(subtopic_id)
            if all_chunks:
                context_parts = [c["content"] for c in all_chunks[:5]]
                context_block = (
                    "[CONTEXT]\n" + "\n---\n".join(context_parts) + "\n[/CONTEXT]"
                )
                messages.append({"role": "user", "content": context_block})

        # 3. Recent message history (last 20)
        history = await self.db.get_messages(subtopic_id, limit=20)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # 4. Current user message
        messages.append({"role": "user", "content": user_message})

        return messages

    async def stream_response(
        self, subtopic_id: str, user_message: str
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Async generator yielding (type, data) tuples.

        Event types:
        - ("text_delta", token) -- raw streaming token
        - ("sentence", text)   -- complete sentence for TTS
        - ("diagram", code)    -- extracted mermaid diagram
        - ("done", "")         -- stream complete

        Also saves user message before streaming and assistant message after.
        Updates progress to "in_progress".
        """
        # Save user message
        await self.db.save_message(subtopic_id, "user", user_message)

        # Update progress
        await self.db.upsert_progress(subtopic_id, "in_progress")

        # Build context
        context = await self.get_context(subtopic_id, user_message)

        # Stream response from LLM
        sentence_buf = SentenceBuffer()
        full_response = ""

        async for token in self.llm.chat_stream(context):
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
                    print(f"[conversation] Diagram generation failed: {e}")

        # Also extract any inline mermaid blocks (fallback)
        inline_diagrams = _MERMAID_BLOCK_RE.findall(full_response)
        for diagram in inline_diagrams:
            stripped = diagram.strip()
            diagrams.append(stripped)
            yield ("diagram", stripped)

        # Save assistant message with diagrams
        await self.db.save_message(
            subtopic_id, "assistant", full_response, diagrams=diagrams or None
        )

        yield ("done", "")
