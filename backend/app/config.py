# backend/app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "study_pal.db"
VECTOR_DIR = DATA_DIR / "vectors"

ZAI_API_KEY = os.getenv("ZAI_API_KEY", "")
ZAI_BASE_URL = "https://api.z.ai/api"
ZAI_MODEL = os.getenv("ZAI_MODEL", "glm-4.7")

TTS_MODEL = "KittenML/kitten-tts-nano-0.8-int8"
TTS_VOICE = "Bella"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
