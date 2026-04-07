"""
Embedding Service - Generates vector embeddings for text.

Uses Sentence Transformers to convert text chunks into
dense vector representations for similarity search.
"""

import logging
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using Sentence Transformers."""

    _model: SentenceTransformer = None  # type: ignore

    @classmethod
    def _get_model(cls) -> SentenceTransformer:
        """Lazy-load the embedding model (singleton)."""
        if cls._model is None:
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding model loaded successfully.")
        return cls._model

    @classmethod
    def generate_embeddings(cls, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of text strings.

        Args:
            texts: List of text strings to embed.

        Returns:
            Numpy array of shape (len(texts), embedding_dim).
        """
        model = cls._get_model()
        embeddings = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )
        logger.info(f"Generated {len(texts)} embeddings of dimension {embeddings.shape[1]}")
        return embeddings.astype(np.float32)

    @classmethod
    def generate_query_embedding(cls, query: str) -> np.ndarray:
        """
        Generate an embedding for a single query string.

        Args:
            query: The query text.

        Returns:
            Numpy array of shape (1, embedding_dim).
        """
        model = cls._get_model()
        embedding = model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding.astype(np.float32)
