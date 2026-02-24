"""WebSocket chat endpoint for live conversation with the AI tutor."""

from __future__ import annotations

import asyncio
import base64
import time

from fastapi import APIRouter, Request
from starlette.websockets import WebSocket, WebSocketDisconnect

router = APIRouter(tags=["chat"])


class Benchmark:
    def __init__(self):
        self.timings: dict[str, float] = {}
        self._starts: dict[str, float] = {}

    def start(self, name: str):
        self._starts[name] = time.perf_counter()

    def end(self, name: str) -> float:
        if name in self._starts:
            elapsed = (time.perf_counter() - self._starts[name]) * 1000
            self.timings[name] = elapsed
            del self._starts[name]
            return elapsed
        return 0

    def to_dict(self) -> dict[str, float]:
        return dict(self.timings)


@router.get("/api/chat/{subtopic_id}/info")
async def get_subtopic_info(request: Request, subtopic_id: str):
    """Return enriched subtopic info: name, section, objectives, course materials."""
    db = request.app.state.db
    import json

    subtopic = await db.get_subtopic(subtopic_id)
    if not subtopic:
        return {"title": "Unknown", "section_title": "", "learning_objectives": [], "materials": []}

    # Get section info
    cursor = await db._db.execute(
        "SELECT s.title, s.learning_objectives, s.course_id FROM sections s JOIN subtopics st ON st.section_id = s.id WHERE st.id = ?",
        (subtopic_id,),
    )
    row = await cursor.fetchone()
    section_title = row[0] if row else ""
    objectives_raw = row[1] if row else "[]"
    course_id = row[2] if row else None

    try:
        objectives = json.loads(objectives_raw)
    except Exception:
        objectives = []

    # Get course materials
    materials = []
    if course_id:
        mats = await db.get_materials_by_course(course_id)
        materials = [{"id": m["id"], "filename": m["filename"]} for m in mats]

    return {
        "title": subtopic["title"],
        "summary": subtopic.get("summary", ""),
        "section_title": section_title,
        "learning_objectives": objectives,
        "materials": materials,
    }


@router.get("/api/chat/{subtopic_id}/messages")
async def get_messages(request: Request, subtopic_id: str):
    """Return chat history for a subtopic."""
    db = request.app.state.db
    messages = await db.get_messages(subtopic_id, limit=100)
    return [
        {"role": m["role"], "content": m["content"], "sources": m.get("sources", [])}
        for m in messages
    ]


@router.delete("/api/chat/{subtopic_id}/messages")
async def clear_messages(request: Request, subtopic_id: str):
    """Delete all messages for a subtopic."""
    db = request.app.state.db
    await db.delete_messages(subtopic_id)
    return {"status": "ok"}


@router.get("/api/chat/course/{course_id}/messages")
async def get_course_messages(request: Request, course_id: str):
    """Return chat history for a course-level chat."""
    db = request.app.state.db
    messages = await db.get_course_messages(course_id, limit=100)
    return [
        {"role": m["role"], "content": m["content"], "sources": m.get("sources", [])}
        for m in messages
    ]


@router.delete("/api/chat/course/{course_id}/messages")
async def clear_course_messages(request: Request, course_id: str):
    """Delete all messages for a course-level chat."""
    db = request.app.state.db
    await db.delete_course_messages(course_id)
    return {"status": "ok"}


@router.websocket("/ws/chat/course/{course_id}")
async def course_chat_ws(websocket: WebSocket, course_id: str):
    """WebSocket endpoint for course-level chat. Same protocol as subtopic chat."""
    await websocket.accept()
    conversation = websocket.app.state.conversation
    tts = websocket.app.state.tts
    stt = websocket.app.state.stt

    tts_tasks: list[asyncio.Task] = []

    async def _generate_tts(sentence: str) -> tuple[bytes | None, float]:
        t0 = time.perf_counter()
        audio = await asyncio.to_thread(tts.generate, sentence)
        elapsed = (time.perf_counter() - t0) * 1000
        return audio, elapsed

    async def _handle_text(user_message: str, mode: str = "chat"):
        tts_tasks.clear()

        async for event_type, event_data in conversation.stream_course_response(
            course_id, user_message, mode=mode
        ):
            if event_type == "text_delta":
                await websocket.send_json({"type": "text_delta", "content": event_data})
            elif event_type == "sentence":
                if tts and event_data and event_data.strip():
                    task = asyncio.create_task(_generate_tts(event_data))
                    tts_tasks.append(task)
            elif event_type == "diagram":
                await websocket.send_json({"type": "diagram", "mermaid": event_data})
            elif event_type == "sources":
                await websocket.send_json({"type": "sources", "sources": event_data})
            elif event_type == "done":
                for task in tts_tasks:
                    try:
                        audio, _tts_time = await task
                        if audio:
                            await websocket.send_json({
                                "type": "audio_chunk",
                                "data": base64.b64encode(audio).decode(),
                            })
                    except Exception:
                        pass
                tts_tasks.clear()
                await websocket.send_json({"type": "done"})

    try:
        while True:
            data = await websocket.receive_json()
            mode = data.get("mode", "chat")

            if data.get("type") == "audio" and stt:
                audio_b64 = data.get("data", "")
                if audio_b64:
                    audio_bytes = base64.b64decode(audio_b64)
                    text = await asyncio.to_thread(stt.transcribe, audio_bytes)
                    if text:
                        await websocket.send_json({"type": "transcript", "content": text})
                        await _handle_text(text, mode=mode)
                continue

            user_message = data.get("content", "")
            if not user_message:
                continue
            await _handle_text(user_message, mode=mode)

    except WebSocketDisconnect:
        pass


@router.websocket("/ws/chat/{subtopic_id}")
async def chat_ws(websocket: WebSocket, subtopic_id: str):
    """WebSocket endpoint for streaming conversation with a subtopic's AI tutor.

    Client sends JSON:
      - {"content": "user message"}           — text message
      - {"type": "audio", "data": "<base64>"}  — audio for STT

    Server sends JSON events:
      - {"type": "text_delta", "content": "..."}
      - {"type": "audio_chunk", "data": "<base64 wav>"}
      - {"type": "diagram", "mermaid": "..."}
      - {"type": "transcript", "content": "..."}  — STT result
      - {"type": "done"}
    """
    await websocket.accept()
    conversation = websocket.app.state.conversation
    tts = websocket.app.state.tts
    stt = websocket.app.state.stt

    tts_tasks: list[asyncio.Task] = []
    bench = Benchmark()
    voice_start_time: float = 0

    async def _generate_tts(sentence: str) -> tuple[bytes | None, float]:
        """Generate TTS audio in a thread. Returns (audio_bytes, elapsed_ms)."""
        t0 = time.perf_counter()
        audio = await asyncio.to_thread(tts.generate, sentence)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[bench] TTS: {elapsed:.0f}ms")
        return audio, elapsed

    async def _handle_text(user_message: str, is_voice: bool = False, mode: str = "chat"):
        """Stream an LLM response for a user message."""
        tts_tasks.clear()
        bench.timings.clear()
        bench.start("llm_total")
        first_token_time = None

        async for event_type, event_data in conversation.stream_response(
            subtopic_id, user_message, mode=mode
        ):
            if first_token_time is None and event_type == "text_delta":
                first_token_time = bench.end("llm_first_token")
                if is_voice and voice_start_time:
                    e2e = (time.perf_counter() - voice_start_time) * 1000
                    print(f"[bench] Voice-to-first-token (E2E): {e2e:.0f}ms")
                    await websocket.send_json(
                        {
                            "type": "benchmark",
                            "data": {
                                "llm_first_token_ms": round(first_token_time),
                                "voice_e2e_ms": round(e2e),
                            },
                        }
                    )
                else:
                    print(f"[bench] LLM first token: {first_token_time:.0f}ms")
                    await websocket.send_json(
                        {
                            "type": "benchmark",
                            "data": {"llm_first_token_ms": round(first_token_time)},
                        }
                    )
            if event_type == "text_delta":
                await websocket.send_json({"type": "text_delta", "content": event_data})
            elif event_type == "sentence":
                if tts and event_data and event_data.strip():
                    task = asyncio.create_task(_generate_tts(event_data))
                    tts_tasks.append(task)
            elif event_type == "diagram":
                await websocket.send_json({"type": "diagram", "mermaid": event_data})
            elif event_type == "sources":
                await websocket.send_json({"type": "sources", "sources": event_data})
            elif event_type == "done":
                llm_total = bench.end("llm_total")
                print(f"[bench] LLM total: {llm_total:.0f}ms")
                # Send TTS audio in sentence order (tasks generated concurrently)
                for task in tts_tasks:
                    try:
                        audio, tts_time = await task
                        if audio:
                            await websocket.send_json(
                                {
                                    "type": "audio_chunk",
                                    "data": base64.b64encode(audio).decode(),
                                    "benchmark": {"tts_ms": round(tts_time)},
                                }
                            )
                    except Exception:
                        pass
                tts_tasks.clear()
                await websocket.send_json(
                    {
                        "type": "done",
                        "benchmark": {"llm_total_ms": round(llm_total)},
                    }
                )

    try:
        while True:
            data = await websocket.receive_json()
            mode = data.get("mode", "chat")

            # Audio message — transcribe locally via faster-whisper
            if data.get("type") == "audio" and stt:
                audio_b64 = data.get("data", "")
                if audio_b64:
                    voice_start_time = time.perf_counter()
                    bench.start("stt")
                    audio_bytes = base64.b64decode(audio_b64)
                    text = await asyncio.to_thread(stt.transcribe, audio_bytes)
                    stt_time = bench.end("stt")
                    print(f"[bench] STT: {stt_time:.0f}ms")
                    await websocket.send_json(
                        {
                            "type": "benchmark",
                            "data": {"stt_ms": round(stt_time)},
                        }
                    )
                    if text:
                        # Send transcript back so frontend can display it
                        await websocket.send_json(
                            {"type": "transcript", "content": text}
                        )
                        # Process as normal message
                        await _handle_text(text, is_voice=True, mode=mode)
                continue

            # Text message
            user_message = data.get("content", "")
            if not user_message:
                continue

            await _handle_text(user_message, mode=mode)

    except WebSocketDisconnect:
        pass
