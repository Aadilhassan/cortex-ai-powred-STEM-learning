import os
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _can_import(module_name: str) -> bool:
    """Check if a module can be imported without crashing (e.g. SIGILL from zvec)."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        capture_output=True,
        timeout=30,
    )
    return result.returncode == 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import (
        DATA_DIR,
        DB_PATH,
        OPENROUTER_API_KEY,
        OPENROUTER_BASE_URL,
        PRIMARY_MODEL,
        DIAGRAM_MODEL,
        GROQ_API_KEY,
        VECTOR_DIR,
    )
    from app.database import Database
    from app.services.llm_client import LLMClient

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    print("[startup] Initializing database...")
    db = Database(str(DB_PATH))
    await db.initialize()
    print("[startup] Database ready")

    primary_llm = LLMClient(api_key=OPENROUTER_API_KEY, model=PRIMARY_MODEL, base_url=OPENROUTER_BASE_URL)
    print(f"[startup] Primary LLM ready ({PRIMARY_MODEL})")

    diagram_llm = LLMClient(api_key=OPENROUTER_API_KEY, model=DIAGRAM_MODEL, base_url=OPENROUTER_BASE_URL)
    print(f"[startup] Diagram LLM ready ({DIAGRAM_MODEL})")

    # Embedder
    embedder = None
    try:
        from app.services.embedder import Embedder

        embedder = Embedder()
        print("[startup] Embedder ready")
    except Exception as e:
        print(f"[startup] Embedder failed: {e}")

    # Vector store — probe in subprocess first (zvec can SIGILL on CPUs without AVX2)
    vector_store = None
    if _can_import("zvec"):
        try:
            from app.services.vector_store import VectorStore

            vector_store = VectorStore(VECTOR_DIR)
            print("[startup] Vector store ready")
        except Exception as e:
            print(f"[startup] Vector store failed: {e}")
    else:
        print("[startup] Vector store skipped (zvec not compatible with this CPU)")

    # TTS (KittenTTS nano - fast, cute neural voices)
    tts = None
    if not os.getenv("TESTING"):
        try:
            from app.services.tts_engine import TTSEngine

            tts = TTSEngine(voice="Kiki")
            print("[startup] TTS ready (KittenTTS nano - Kiki)")
        except Exception as e:
            print(f"[startup] TTS failed: {e}")

    # STT (Groq whisper-large-v3-turbo)
    stt = None
    if not os.getenv("TESTING"):
        try:
            from app.services.stt_engine import STTEngine

            stt = STTEngine(api_key=GROQ_API_KEY)
            print("[startup] STT ready (Groq Whisper)")
        except Exception as e:
            print(f"[startup] STT failed: {e}")

    # Wire up services
    from app.services.conversation import ConversationManager
    from app.services.diagram_service import DiagramService
    from app.services.handout_processor import HandoutProcessor
    from app.services.quiz_generator import QuizGenerator

    diagram_service = DiagramService(diagram_llm)

    app.state.db = db
    app.state.primary_llm = primary_llm
    app.state.diagram_llm = diagram_llm
    app.state.embedder = embedder
    app.state.vector_store = vector_store
    app.state.tts = tts
    app.state.stt = stt
    app.state.diagram_service = diagram_service
    app.state.handout_processor = HandoutProcessor(db, primary_llm, embedder, vector_store)
    app.state.conversation = ConversationManager(db, primary_llm, embedder, vector_store, diagram_service)
    app.state.quiz_generator = QuizGenerator(db, primary_llm)

    print("[startup] All services initialized!")

    yield

    await primary_llm.close()
    await diagram_llm.close()
    await db.close()


app = FastAPI(title="Study Pal", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import chat, courses, diagrams, progress, quiz

app.include_router(courses.router, prefix="/api")
app.include_router(chat.router)
app.include_router(quiz.router, prefix="/api")
app.include_router(diagrams.router, prefix="/api")
app.include_router(progress.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
