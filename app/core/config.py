"""
Application configuration using Pydantic Settings.

Loads environment variables from .env file and validates them.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Groq
    GROQ_API_KEY: str = ""

    # Database (SQLite by default for local dev)
    DATABASE_URL: str = "sqlite:///./data/docqa.db"

    # Embedding model
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # FAISS index storage path
    FAISS_INDEX_PATH: str = "./data/faiss_index"

    # Upload directory
    UPLOAD_DIR: str = "./data/uploads"

    # LLM settings (Groq + llama)
    LLM_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    LLM_MAX_TOKENS: int = 4000

    # Chunking settings
    CHUNK_SIZE: int = 600  # tokens (500-800 range)
    CHUNK_OVERLAP: int = 120  # tokens (100-150 range)

    # Retrieval settings
    TOP_K: int = 5

    # Embedding dimension for all-MiniLM-L6-v2
    EMBEDDING_DIM: int = 384

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
