import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import (
        DATA_DIR,
        DB_PATH,
        EMBEDDING_MODEL,
        GROQ_API_KEY,
        GROQ_BASE_URL,
        OPENROUTER_API_KEY,
        OPENROUTER_BASE_URL,
        PRIMARY_MODEL,
        DIAGRAM_MODEL,
    )
    from app.database import Database
    from app.services.llm_client import LLMClient

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("[startup] Initializing database...")
    db = Database(str(DB_PATH))
    await db.initialize()
    print("[startup] Database ready")

    primary_llm = LLMClient(api_key=GROQ_API_KEY, model=PRIMARY_MODEL, base_url=GROQ_BASE_URL)
    print(f"[startup] Primary LLM ready ({PRIMARY_MODEL} via Groq)")

    diagram_llm = LLMClient(api_key=OPENROUTER_API_KEY, model=DIAGRAM_MODEL, base_url=OPENROUTER_BASE_URL, timeout=30.0)
    print(f"[startup] Diagram LLM ready ({DIAGRAM_MODEL})")

    # Embedder (OpenRouter API)
    embedder = None
    try:
        from app.services.embedder import Embedder

        embedder = Embedder(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model=EMBEDDING_MODEL,
        )
        print(f"[startup] Embedder ready ({EMBEDDING_MODEL} via OpenRouter)")
    except Exception as e:
        print(f"[startup] Embedder failed: {e}")

    # Vector store (numpy + SQLite — no native extensions)
    from app.services.vector_store import VectorStore

    vector_store = VectorStore(db)
    print("[startup] Vector store ready (numpy+SQLite)")

    # TTS (Groq Orpheus)
    tts = None
    if not os.getenv("TESTING"):
        try:
            from app.services.tts_engine import TTSEngine

            tts = TTSEngine(api_key=GROQ_API_KEY, voice="autumn")
            print("[startup] TTS ready (Groq Orpheus - autumn)")
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
    app.state.handout_processor = HandoutProcessor(db, primary_llm, embedder)
    app.state.conversation = ConversationManager(db, primary_llm, embedder, vector_store, diagram_service)
    app.state.quiz_generator = QuizGenerator(db, primary_llm)

    print("[startup] All services initialized!")

    yield

    await primary_llm.close()
    await diagram_llm.close()
    if embedder:
        await embedder.close()
    await db.close()


app = FastAPI(title="Cortex", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import chat, courses, diagrams, exam, progress, quiz

app.include_router(courses.router, prefix="/api")
app.include_router(chat.router)
app.include_router(exam.router)
app.include_router(quiz.router, prefix="/api")
app.include_router(diagrams.router, prefix="/api")
app.include_router(progress.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
