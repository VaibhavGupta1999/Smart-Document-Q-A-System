"""
Smart Document Q&A System - FastAPI Application Entry Point.

This module initializes the FastAPI application, includes all routers,
sets up CORS, mounts static files, and loads the FAISS index on startup.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine, Base
from app.core.vector_store import vector_store_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    # --- Startup ---
    logger.info("Starting Smart Document Q&A System...")

    # Create database tables (Alembic handles migrations, but this is a fallback)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured.")

    # Ensure data directories exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    logger.info("Data directories ensured.")

    # Load FAISS index from disk if available
    vector_store_manager.load_index()
    logger.info("FAISS index loaded (or initialized fresh).")

    yield

    # --- Shutdown ---
    logger.info("Shutting down Smart Document Q&A System...")
    vector_store_manager.save_index()
    logger.info("FAISS index saved to disk.")


# Create FastAPI app
app = FastAPI(
    title="Smart Document Q&A System",
    description="A production-grade document question answering system with RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")

# Mount static files for frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def serve_frontend() -> FileResponse:
    """Serve the frontend HTML page."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    )


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Smart Document Q&A System",
        "version": "1.0.0",
    }
