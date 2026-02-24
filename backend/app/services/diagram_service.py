"""Dedicated Mermaid diagram generation using a code-focused LLM."""

from __future__ import annotations

import re

# Regex to strip markdown code fences: ```mermaid ... ``` or ``` ... ```
_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)

_DIAGRAM_PROMPT = """\
Generate a Mermaid diagram about the following topic.

Rules:
- Output ONLY the Mermaid code — no markdown fences, no explanation, no commentary
- Use simple labels without special characters
- Do NOT use parentheses inside [] node labels
- Do NOT include style, classDef, or class lines
- Make the diagram clear, focused, and easy to read
{type_hint}{context_hint}
Topic: {topic}
"""


class DiagramService:
    """Generates Mermaid diagrams via a code-focused LLM."""

    def __init__(self, llm) -> None:
        self.llm = llm

    async def generate(
        self,
        topic: str,
        context: str | None = None,
        diagram_type: str | None = None,
    ) -> str:
        """Generate and return Mermaid diagram code for the given topic.

        Args:
            topic: The subject to create a diagram about.
            context: Optional additional context to guide generation.
            diagram_type: Optional Mermaid diagram type hint (e.g. "flowchart", "sequenceDiagram").

        Returns:
            Clean Mermaid code string with no markdown fences.
        """
        type_hint = f"\n- Use diagram type: {diagram_type}" if diagram_type else ""
        context_hint = f"\n\nAdditional context:\n{context}" if context else ""

        prompt = _DIAGRAM_PROMPT.format(
            topic=topic,
            type_hint=type_hint,
            context_hint=context_hint,
        )

        messages = [{"role": "user", "content": prompt}]
        raw = await self.llm.chat(messages, temperature=0.3)

        return _strip_fences(raw)


def _strip_fences(text: str) -> str:
    """Remove accidental markdown code fences from LLM output."""
    text = text.strip()
    fence_match = _FENCE_RE.match(text)
    if fence_match:
        return fence_match.group(1).strip()
    return text
