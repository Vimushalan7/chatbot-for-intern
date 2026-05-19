"""
config.py
---------
Central configuration for the Research Paper AI Assistant backend.
All environment-driven settings live here; nothing is hardcoded elsewhere.
"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "Research Paper AI Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Ollama LLM ─────────────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"          # change to any model pulled via `ollama pull`
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"  # lightweight embedding model

    # ── Vector Store (ChromaDB) ────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "research_papers"

    # ── PDF Upload ─────────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 50              # 50 MB upload limit

    # ── RAG Pipeline ──────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 1000                  # characters per chunk
    CHUNK_OVERLAP: int = 200               # overlap between chunks
    TOP_K_RESULTS: int = 3                 # number of chunks retrieved per query

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = ["*"]          # tighten this in production

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Singleton settings object used throughout the app
settings = Settings()

# Ensure required directories exist on first import
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
