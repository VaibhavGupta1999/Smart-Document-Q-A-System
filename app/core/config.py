import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file to allow GROQ_API_KEY to be picked up if present
load_dotenv()

class Settings(BaseSettings):
    """
    Application configuration.
    
    Only GROQ_API_KEY and HF_API_TOKEN are loaded from the environment/env file.
    All other settings are hardcoded into the system for consistency.
    """

    # API Keys - Dynamic environment variables
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    HF_API_TOKEN: str = os.getenv("HF_API_TOKEN", "")

    # HuggingFace Inference API configuration
    HF_API_URL: str = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"

    # Hardcoded Database configuration
    DATABASE_URL: str = "sqlite:///./data/docqa.db"

    # Hardcoded Embedding Model
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Hardcoded FAISS storage path
    FAISS_INDEX_PATH: str = "./data/faiss_index"

    # Hardcoded Upload Storage
    UPLOAD_DIR: str = "./data/uploads"

    # Hardcoded LLM settings
    LLM_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    LLM_MAX_TOKENS: int = 4000

    # Internal logic settings
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 120
    TOP_K: int = 5
    EMBEDDING_DIM: int = 384

    class Config:
        # We handle .env loading manually above to ensure only chosen vars are dynamic
        case_sensitive = True


settings = Settings()
