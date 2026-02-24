# backend/app/config.py
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "study_pal.db"

# Groq (conversation LLM + STT)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
PRIMARY_MODEL = "openai/gpt-oss-120b"

# OpenRouter (diagram generation only)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DIAGRAM_MODEL = "deepseek/deepseek-v3.2"

EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
