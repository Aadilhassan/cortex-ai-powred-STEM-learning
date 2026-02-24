"""Dedicated Mermaid diagram generation using a code-focused LLM."""

from __future__ import annotations

import re

# Regex to strip markdown code fences: ```mermaid ... ``` or ``` ... ```
_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)

_DIAGRAM_PROMPT = """\
Generate a Mermaid.js flowchart about the following topic.

STRICT SYNTAX RULES — violating these will crash the renderer:
1. Every node label MUST be on a SINGLE LINE. NEVER put a newline inside [...] or {{...}}.
2. For multi-detail labels, use <br/> inside quoted brackets: ["Line 1<br/>Line 2"]
3. No parentheses inside [] — use ["label with (parens)"] instead
4. No style, classDef, or class lines
5. Use simple arrows: -->, --->, -->|label|
6. Keep it simple: 6-12 nodes max
7. Output ONLY the Mermaid code. No markdown fences, no explanation.

CORRECT example:
flowchart TD
    A["Start"] --> B["Step 1<br/>Details here"]
    B --> C{{"Decision?"}}
    C -->|Yes| D["Result A"]
    C -->|No| E["Result B"]
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
        """Generate and return Mermaid diagram code for the given topic."""
        type_hint = f"\n- Use diagram type: {diagram_type}" if diagram_type else ""
        context_hint = f"\n\nAdditional context:\n{context}" if context else ""

        prompt = _DIAGRAM_PROMPT.format(
            topic=topic,
            type_hint=type_hint,
            context_hint=context_hint,
        )

        messages = [{"role": "user", "content": prompt}]
        raw = await self.llm.chat(messages, temperature=0.3, max_tokens=500)

        code = _strip_fences(raw)
        code = _sanitize_mermaid(code)
        return code


def _strip_fences(text: str) -> str:
    """Remove accidental markdown code fences from LLM output."""
    text = text.strip()
    fence_match = _FENCE_RE.match(text)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def _sanitize_mermaid(code: str) -> str:
    """Fix common LLM mermaid mistakes that crash the renderer."""
    lines = code.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Remove style/classDef/class lines
        stripped = line.strip()
        if stripped and re.match(r"^(style|classDef|class)\s", stripped):
            i += 1
            continue

        # Detect broken multiline labels: a line with [...  or {... that doesn't close
        # Merge continuation lines until the bracket closes
        open_bracket = None
        close_bracket = None
        for bracket_open, bracket_close in [("[", "]"), ("{", "}")]:
            # Count opens and closes in the line
            opens = line.count(bracket_open)
            closes = line.count(bracket_close)
            if opens > closes:
                open_bracket = bracket_open
                close_bracket = bracket_close
                break

        if open_bracket and close_bracket:
            # Merge lines until bracket closes
            merged = line
            while i + 1 < len(lines) and merged.count(open_bracket) > merged.count(close_bracket):
                i += 1
                # Join with <br/> for label content
                next_line = lines[i].strip()
                if next_line:
                    merged = merged.rstrip() + "<br/>" + next_line
            line = merged

        result.append(line)
        i += 1

    code = "\n".join(result)

    # Fix doubled quotes: [""text""] → ["text"]
    code = re.sub(r'\[""+', '["', code)
    code = re.sub(r'""+\]', '"]', code)

    # Quote any [...] labels that contain <br/> or parentheses but aren't quoted
    code = re.sub(
        r'\[([^\]"]*(?:<br/>|\()[^\]"]*)\]',
        r'["\1"]',
        code,
    )

    # Fix -->|label|> to -->|label|
    code = re.sub(r"(--[->])\|([^|]*)\|>", r"\1|\2|", code)

    # Collapse excessive blank lines
    code = re.sub(r"\n{3,}", "\n\n", code)

    return code.strip()
