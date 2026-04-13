import logging
import time
from typing import List

import httpx
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using HuggingFace Inference API."""

    @staticmethod
    def _call_api(texts: List[str]) -> np.ndarray:
        """
        Call the HuggingFace Inference API for embeddings.
        Includes basic retry logic for service availability.
        """
        if not settings.HF_API_TOKEN:
            logger.warning("HF_API_TOKEN is missing. API calls may fail or be heavily rate-limited.")

        headers = {"Authorization": f"Bearer {settings.HF_API_TOKEN}"} if settings.HF_API_TOKEN else {}
        
        # HuggingFace API can be cold; we try up to 3 times
        for attempt in range(3):
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        settings.HF_API_URL,
                        headers=headers,
                        json={"inputs": texts, "options": {"wait_for_model": True}}
                    )
                
                if response.status_code == 200:
                    data = response.json()
                    # HF API returns a 2D list for multiple inputs, or 1D for single
                    # We ensure we have a 2D array for consistency
                    embeddings = np.array(data)
                    
                    # If it's a 1D array (from a single string), reshape it
                    if len(embeddings.shape) == 1:
                        embeddings = embeddings.reshape(1, -1)
                        
                    return embeddings.astype(np.float32)
                
                elif response.status_code == 503:
                    # Model is loading
                    logger.info("HF model is loading, retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    logger.error(f"HF API error {response.status_code}: {response.text}")
                    break
                    
            except Exception as e:
                logger.error(f"Error calling HF API: {e}")
                if attempt < 2:
                    time.sleep(2)
                
        # Fallback: Return zero embeddings if API fails completely
        # This prevents the whole app from crashing, though search will be broken
        logger.error("All HF API attempts failed. Returning zero embeddings as fallback.")
        return np.zeros((len(texts), settings.EMBEDDING_DIM), dtype=np.float32)

    @classmethod
    def generate_embeddings(cls, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of text strings via API.

        Args:
            texts: List of text strings to embed.

        Returns:
            Numpy array of shape (len(texts), embedding_dim).
        """
        logger.info(f"Generating {len(texts)} embeddings via HuggingFace API")
        return cls._call_api(texts)

    @classmethod
    def generate_query_embedding(cls, query: str) -> np.ndarray:
        """
        Generate an embedding for a single query string via API.

        Args:
            query: The query text.

        Returns:
            Numpy array of shape (1, embedding_dim).
        """
        return cls._call_api([query])
