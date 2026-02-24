# OpenRouter Multi-Model Architecture

**Date:** 2026-02-24
**Status:** Approved

## Summary

Migrate from Groq to OpenRouter as the sole LLM provider. Use two specialized models:

- **MiniMax M2.5** (`minimax/minimax-m2.5`) — course creation, conversation/tutoring, quiz generation
- **Codestral** (`mistralai/codestral-2501`) — diagram generation (in-chat delegation + dedicated endpoint)

STT stays on Groq (Whisper) since OpenRouter doesn't offer speech-to-text.

## Models

| Role | Model | Provider | Why |
|------|-------|----------|-----|
| Course creation | MiniMax M2.5 | OpenRouter | Strong structured extraction, good reasoning |
| Conversation | MiniMax M2.5 | OpenRouter | Fast, capable chat model |
| Quiz generation | MiniMax M2.5 | OpenRouter | Good at generating diverse question types |
| Diagram generation | Codestral 2501 | OpenRouter | Low latency, high throughput, code-focused |
| Speech-to-text | Whisper Large v3 Turbo | Groq | Stays as-is, separate from LLM pipeline |

## Changes by File

### 1. `config.py`

- Remove `GROQ_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`
- Add `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"`
- Add `PRIMARY_MODEL = "minimax/minimax-m2.5"`
- Add `DIAGRAM_MODEL = "mistralai/codestral-2501"`
- Keep `GROQ_API_KEY` only for STT engine

### 2. `llm_client.py`

- Support instantiating multiple clients with different models
- Both clients share the same OpenRouter base URL and API key, differ only in model
- No special token handling needed (MiniMax M2.5 is standard chat completion)

### 3. `handout_processor.py`

- Uses primary client (MiniMax M2.5)
- Enhanced prompt extracts:
  - Course `name` and `description` (auto-extracted, user doesn't provide these)
  - Sections with `title`, `summary`, `learning_objectives`, `key_concepts`, `prerequisites`
  - Subtopics with `title`, `content`, `summary`
- Returns richer structure to the router

### 4. `courses.py` (router)

- `POST /api/courses` — simplified: accepts only `handout_text` (no required `name`/`description`)
- `POST /api/courses/upload` — simplified: accepts only the file (no required `name`/`description`)
- Name and description come from LLM extraction
- Returns the auto-extracted name/description in the response

### 5. `conversation.py`

- Uses primary client (MiniMax M2.5) for tutoring
- When tutor wants a diagram: instead of emitting Mermaid inline, the tutor signals a diagram request (e.g., `[DIAGRAM: topic description]`)
- Conversation service detects the signal and delegates to the diagram service
- Diagram result is emitted as a separate `diagram` event in the stream

### 6. New: `diagram_service.py`

- Dedicated service using diagram client (Codestral)
- `generate_diagram(topic, context=None, diagram_type=None) -> str` — returns Mermaid code
- Prompt instructs the model to output only valid Mermaid syntax
- Called from conversation service and from the REST endpoint

### 7. New: diagram endpoint in router

- `POST /api/diagrams` — accepts `{ topic, context?, diagram_type? }`
- Returns `{ mermaid: "..." }`
- Uses the diagram service directly

### 8. `quiz_generator.py`

- Uses primary client (MiniMax M2.5)
- No structural changes, just swap the client

### 9. `database.py`

- Add columns to `sections` table: `learning_objectives` (JSON), `key_concepts` (JSON), `prerequisites` (JSON)
- Migration: add columns if they don't exist (ALTER TABLE with IF NOT EXISTS pattern)

### 10. `main.py`

- Initialize two LLM clients: `primary_llm` and `diagram_llm`
- Initialize new `DiagramService` with the diagram client
- Wire both into services that need them
- Update CORS if needed

### 11. Frontend (minimal changes)

- `DiagramPanel.tsx` — no changes needed, it already renders Mermaid strings
- `StudyView.tsx` — optionally add a "Generate Diagram" button that calls `POST /api/diagrams`
- Course creation form — remove name/description fields, show auto-extracted values after upload

## Environment Variables

```
OPENROUTER_API_KEY=sk-or-v1-...    # For all LLM calls
GROQ_API_KEY=...                    # Only for STT (Whisper)
```

## Data Flow: Course Creation

```
User uploads PDF/pastes text
  -> courses router (no name/description needed)
  -> handout_processor.process()
  -> MiniMax M2.5 via OpenRouter
  -> Returns: { name, description, sections: [{ title, summary, learning_objectives, key_concepts, prerequisites, subtopics: [...] }] }
  -> Store in DB
  -> Return course with auto-extracted metadata
```

## Data Flow: Diagram in Conversation

```
User sends message
  -> conversation.stream_response()
  -> MiniMax M2.5 streams tutor response
  -> If tutor includes [DIAGRAM: ...] signal
     -> diagram_service.generate_diagram(topic, context)
     -> Codestral via OpenRouter
     -> Returns Mermaid code
     -> Emitted as diagram event to WebSocket
```

## Data Flow: On-Demand Diagram

```
POST /api/diagrams { topic, context?, diagram_type? }
  -> diagram_service.generate_diagram()
  -> Codestral via OpenRouter
  -> Returns { mermaid: "..." }
```
