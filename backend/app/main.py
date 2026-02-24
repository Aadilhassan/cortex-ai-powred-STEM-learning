from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import DB_PATH, VECTOR_DIR, ZAI_API_KEY, ZAI_MODEL, DATA_DIR
    from app.database import Database
    from app.services.llm_client import LLMClient
    from app.services.embedder import Embedder
    from app.services.vector_store import VectorStore
    from app.services.handout_processor import HandoutProcessor
    from app.services.conversation import ConversationManager
    from app.services.quiz_generator import QuizGenerator

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    db = Database(DB_PATH)
    await db.initialize()
    llm = LLMClient(api_key=ZAI_API_KEY, model=ZAI_MODEL)
    embedder = Embedder()
    vector_store = VectorStore(VECTOR_DIR)

    # TTS is optional -- may fail if kittentts not installed
    tts = None
    if not os.getenv("TESTING"):
        try:
            from app.services.tts_engine import TTSEngine
            tts = TTSEngine()
        except Exception:
            pass

    app.state.db = db
    app.state.llm = llm
    app.state.embedder = embedder
    app.state.vector_store = vector_store
    app.state.tts = tts
    app.state.handout_processor = HandoutProcessor(db, llm, embedder, vector_store)
    app.state.conversation = ConversationManager(db, llm, embedder, vector_store)
    app.state.quiz_generator = QuizGenerator(db, llm)

    yield

    await llm.close()
    await db.close()


app = FastAPI(title="Study Pal", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import courses, chat, quiz, progress

app.include_router(courses.router, prefix="/api")
app.include_router(chat.router)
app.include_router(quiz.router, prefix="/api")
app.include_router(progress.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
