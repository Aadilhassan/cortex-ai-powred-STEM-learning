# Study Pal — Design Document

**Date:** 2026-02-24
**Author:** Aadil
**Status:** Approved

## Overview

A local-first, STEM-focused AI study companion that enables real-time voice conversations with an AI tutor. Users create courses from handouts, and the AI breaks them into sections and subtopics. Users then study section-by-section through live voice conversations, with the AI proactively drawing Mermaid diagrams to explain concepts. Quizzes can be generated at topic, subtopic, or course level.

Built for personal use. Single-user, desktop-only, no auth.

## Tech Stack

| Component | Technology | Role |
|---|---|---|
| LLM | Z.ai Coding Plan API (GLM-5/4.7) | Chat, section extraction, quiz generation |
| TTS | KittenTTS (local, CPU-only) | AI voice output, sentence-by-sentence streaming |
| STT | Browser Web Speech API | User voice input, free, zero dependencies |
| Vector DB | zvec (Alibaba, in-process) | Semantic search over course chunks |
| Diagrams | Mermaid.js | Rendered in frontend from AI-generated code |
| Frontend | Astro SPA + React islands | UI, audio playback, diagram rendering |
| Backend | Python FastAPI | API, WebSocket, orchestration |
| Database | SQLite | Courses, sections, messages, quizzes, progress |
| PDF Parsing | PyMuPDF | Extract text from uploaded PDFs |
| Package Mgr | uv (Python), npm (frontend) | Dependency management |

## Architecture

Monolith: single FastAPI server + Astro SPA. No containerization. Run locally with `python` + `astro dev`.

```
Browser (Astro SPA)
  ├── Web Speech API (STT)
  ├── Mermaid.js (diagrams)
  ├── Audio player (TTS playback queue)
  └── WebSocket + REST ──► Python FastAPI
                              ├── Z.ai API (LLM)
                              ├── KittenTTS (local)
                              ├── zvec (vector search)
                              ├── PyMuPDF (PDF parse)
                              └── SQLite (all persistent data)
```

## Data Model

```
Course → Section → Subtopic → Chunk (vector indexed)
                            → Message (conversation history)
                            → Quiz
                            → Progress
```

### Tables

**Course**
- id, name, description, created_at, handout_raw

**Section**
- id, course_id, title, summary, order_index

**Subtopic**
- id, section_id, title, content, summary, order_index

**Chunk**
- id, subtopic_id, content, order_index
- (embedding stored in zvec, linked by chunk_id)

**Message**
- id, subtopic_id, role (user/assistant/system), content, diagrams (JSON array of Mermaid code strings), created_at

**Quiz**
- id, course_id, section_id (nullable), subtopic_id (nullable), scope (topic/subtopic/course), questions (JSON), created_at

**QuizAttempt**
- id, quiz_id, answers (JSON), score, completed_at

**Progress**
- id, subtopic_id, status (not_started/in_progress/completed), last_active, notes

## Core Flows

### Flow 1: Course Creation & Handout Processing

1. User uploads PDF / pastes text / drops file
2. Backend extracts text (PyMuPDF for PDF, direct for text/markdown)
3. Full text sent to Z.ai LLM: "Parse this course handout into sections and subtopics. Return JSON: [{title, summary, subtopics: [{title, content, summary}]}]"
4. For each subtopic:
   - Create Section + Subtopic rows in SQLite
   - Split content into ~500-token chunks with 50-token overlap
   - Generate embeddings (Z.ai embedding API or local all-MiniLM-L6-v2)
   - Index chunks in zvec
5. Course dashboard shows sections/subtopics tree with progress indicators

### Flow 2: Live Conversation Session

1. User opens a subtopic → frontend connects WebSocket to `/ws/chat/:subtopicId`
2. Backend loads: subtopic content + summary, previous message history, system prompt
3. System prompt instructs AI to be a STEM tutor, proactively use Mermaid diagrams, wrap in ` ```mermaid ``` ` blocks
4. User speaks → Web Speech API transcribes → text sent via WebSocket
5. Backend builds context: system prompt + subtopic content + recent messages + vector search (top 5 relevant chunks) → sends to Z.ai streaming API
6. Token stream processed:
   - Text accumulated and sent to frontend via WebSocket
   - Frontend renders markdown + extracts Mermaid diagrams to diagram panel
   - Each completed sentence → KittenTTS → audio bytes → base64 → WebSocket → frontend audio queue
7. Full message saved to SQLite

### Flow 3: Quiz Generation

1. User selects quiz scope (topic/subtopic/course)
2. Backend gathers relevant chunks for that scope
3. Sends to Z.ai: "Generate quiz with MCQ, short-answer, and diagram-based questions. Return JSON."
4. Quiz rendered: MCQ → radio buttons, short answer → text input (AI evaluates), diagram-based → Mermaid + question
5. Answers submitted → scored → stored → progress updated

## Real-time Conversation Pipeline

```
YOU SPEAK           LLM STREAMS         AI SPEAKS
──────────          ──────────          ──────────
Web Speech API      Z.ai first token    Sentence 1 audio
(near instant) ──►  in ~500ms     ──►   plays immediately
                    Sentence 1           while sentence 2
                    complete    ──►      generates in parallel
                    KittenTTS
                    (~100-300ms)
```

Pipelining ensures audio for sentence N plays while sentence N+1 is being generated. User experiences ~1 second pause after speaking, then the AI responds fluently.

A "thinking" indicator (pulsing dot) shows during the brief gap.

## Frontend

### Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — list courses, create new |
| `/course/:id` | Course overview — sections/subtopics tree, progress |
| `/study/:subtopicId` | Conversation view (main study interface) |
| `/quiz/:quizId` | Active quiz view |

### Conversation View Layout

Split-pane: chat panel (left) + collapsible diagram panel (right).

- Chat panel: message history, markdown rendering, voice input indicator
- Diagram panel: auto-updates with latest AI-generated Mermaid diagram, scrollable history of previous diagrams, collapsible via toggle button
- Bottom bar: mic button (Web Speech API toggle), text input fallback, send button, TTS on/off toggle

### Interactive Components (React Islands)

- ChatPanel.tsx — WebSocket messages, markdown rendering
- DiagramPanel.tsx — Mermaid.js rendering, diagram history
- AudioController.tsx — TTS audio queue, sequential playback
- VoiceInput.tsx — Web Speech API integration
- QuizQuestion.tsx — MCQ/short-answer/diagram-based rendering

## Backend

### API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/courses` | Create course + upload handout |
| GET | `/api/courses` | List all courses |
| GET | `/api/courses/:id` | Course detail with sections/subtopics tree |
| DELETE | `/api/courses/:id` | Delete course and all related data |
| WS | `/ws/chat/:subtopicId` | WebSocket for live conversation |
| POST | `/api/quiz/generate` | Generate quiz for scope |
| POST | `/api/quiz/:id/submit` | Submit quiz answers |
| GET | `/api/quiz/:id` | Get quiz with questions |
| GET | `/api/progress/:courseId` | Progress overview |

### Services

- **HandoutProcessor** — PDF text extraction, LLM section/subtopic extraction, chunking, embedding, zvec indexing
- **ConversationManager** — WebSocket session management, LLM context building (system prompt + history + vector chunks), Z.ai streaming, sentence detection
- **TTSEngine** — KittenTTS wrapper, runs in async thread pool, generates audio per sentence
- **QuizGenerator** — Scope-based chunk gathering, LLM quiz generation, scoring (MCQ auto-graded, short-answer LLM-evaluated)
- **VectorStore** — zvec wrapper, embedding storage, similarity search
- **LLMClient** — Z.ai API wrapper, streaming + non-streaming calls

## Project Structure

```
study-pal/
├── frontend/
│   ├── src/
│   │   ├── layouts/Layout.astro
│   │   ├── pages/
│   │   │   ├── index.astro
│   │   │   ├── course/[id].astro
│   │   │   ├── study/[subtopicId].astro
│   │   │   └── quiz/[quizId].astro
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── DiagramPanel.tsx
│   │   │   ├── AudioController.tsx
│   │   │   ├── VoiceInput.tsx
│   │   │   ├── CourseCard.astro
│   │   │   ├── SectionTree.astro
│   │   │   ├── QuizQuestion.tsx
│   │   │   └── ProgressBar.astro
│   │   └── lib/
│   │       ├── websocket.ts
│   │       └── api.ts
│   ├── astro.config.mjs
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── routers/
│   │   │   ├── courses.py
│   │   │   ├── quiz.py
│   │   │   └── progress.py
│   │   ├── services/
│   │   │   ├── handout_processor.py
│   │   │   ├── conversation.py
│   │   │   ├── tts_engine.py
│   │   │   ├── quiz_generator.py
│   │   │   ├── vector_store.py
│   │   │   └── llm_client.py
│   │   └── config.py
│   ├── data/
│   │   ├── study_pal.db
│   │   └── vectors/
│   └── pyproject.toml
└── docs/plans/
```

## Error Handling

- **Z.ai API down/slow** — "AI is thinking..." with 30s timeout, then retry option. Chat history and diagrams remain accessible.
- **TTS fails** — Graceful degradation: text streams normally, toast "Voice unavailable."
- **PDF parse fails** — Error message, offer manual text paste fallback.
- **WebSocket disconnect** — Auto-reconnect with exponential backoff. Messages persisted server-side, no data loss.

## Out of Scope (YAGNI)

- No multi-user / auth (personal use)
- No mobile-responsive layout (desktop only)
- No export/share
- No spaced repetition / flashcards
- No video/image support in handouts (text-only extraction)
- No custom voice training
