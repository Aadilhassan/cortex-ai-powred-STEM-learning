"""WebSocket chat endpoint for live conversation with the AI tutor."""

from __future__ import annotations

import asyncio
import base64

from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

router = APIRouter(tags=["chat"])


@router.websocket("/ws/chat/{subtopic_id}")
async def chat_ws(websocket: WebSocket, subtopic_id: str):
    """WebSocket endpoint for streaming conversation with a subtopic's AI tutor.

    Client sends JSON: {"content": "user message"}
    Server sends JSON events:
      - {"type": "text_delta", "content": "..."}
      - {"type": "audio_chunk", "data": "<base64 wav>"}
      - {"type": "diagram", "mermaid": "..."}
      - {"type": "done"}
    """
    await websocket.accept()
    conversation = websocket.app.state.conversation
    tts = websocket.app.state.tts

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("content", "")
            if not user_message:
                continue

            async for event_type, event_data in conversation.stream_response(
                subtopic_id, user_message
            ):
                if event_type == "text_delta":
                    await websocket.send_json(
                        {"type": "text_delta", "content": event_data}
                    )
                elif event_type == "sentence":
                    if tts and event_data:
                        audio_bytes = await asyncio.to_thread(
                            tts.generate, event_data
                        )
                        if audio_bytes:
                            await websocket.send_json(
                                {
                                    "type": "audio_chunk",
                                    "data": base64.b64encode(
                                        audio_bytes
                                    ).decode(),
                                }
                            )
                elif event_type == "diagram":
                    await websocket.send_json(
                        {"type": "diagram", "mermaid": event_data}
                    )
                elif event_type == "done":
                    await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass
