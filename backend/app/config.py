# backend/app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "study_pal.db"
VECTOR_DIR = DATA_DIR / "vectors"

# OpenRouter (primary LLM provider)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PRIMARY_MODEL = "minimax/minimax-m2.5"
DIAGRAM_MODEL = "mistralai/codestral-2501"

# Groq (STT only)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
