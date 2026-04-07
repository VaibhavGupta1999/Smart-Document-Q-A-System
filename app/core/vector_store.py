"""
FAISS Vector Store Manager.

Manages the FAISS index for storing and searching document chunk embeddings.
Supports saving/loading the index to/from disk and maintains a metadata
mapping from FAISS internal IDs to (chunk_id, document_id) pairs.
"""

import json
import logging
import os
import threading
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """
    Thread-safe FAISS index manager.

    Stores embeddings and maintains a mapping from FAISS index IDs
    to (chunk_id, document_id) pairs for retrieval.
    """

    def __init__(self, dimension: int = settings.EMBEDDING_DIM) -> None:
        self.dimension = dimension
        self.index: Optional[faiss.IndexFlatIP] = None
        self.id_mapping: Dict[int, Dict[str, int]] = {}  # faiss_id -> {chunk_id, document_id}
        self._lock = threading.Lock()
        self._next_id: int = 0
        self._index_file = os.path.join(settings.FAISS_INDEX_PATH, "index.faiss")
        self._mapping_file = os.path.join(settings.FAISS_INDEX_PATH, "mapping.json")

    def _initialize_index(self) -> None:
        """Create a fresh FAISS index using inner product (cosine similarity with normalized vectors)."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.id_mapping = {}
        self._next_id = 0
        logger.info(f"Initialized fresh FAISS index with dimension {self.dimension}")

    def load_index(self) -> None:
        """Load the FAISS index and metadata mapping from disk."""
        with self._lock:
            if os.path.exists(self._index_file) and os.path.exists(self._mapping_file):
                try:
                    self.index = faiss.read_index(self._index_file)
                    with open(self._mapping_file, "r") as f:
                        raw_mapping = json.load(f)
                    # Convert string keys back to int
                    self.id_mapping = {int(k): v for k, v in raw_mapping.items()}
                    self._next_id = max(self.id_mapping.keys(), default=-1) + 1
                    logger.info(
                        f"Loaded FAISS index with {self.index.ntotal} vectors, "
                        f"mapping has {len(self.id_mapping)} entries"
                    )
                except Exception as e:
                    logger.error(f"Error loading FAISS index: {e}. Initializing fresh.")
                    self._initialize_index()
            else:
                logger.info("No existing FAISS index found. Initializing fresh.")
                self._initialize_index()

    def save_index(self) -> None:
        """Persist the FAISS index and metadata mapping to disk."""
        with self._lock:
            if self.index is None:
                logger.warning("No index to save.")
                return
            try:
                os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
                faiss.write_index(self.index, self._index_file)
                with open(self._mapping_file, "w") as f:
                    json.dump(self.id_mapping, f)
                logger.info(f"Saved FAISS index with {self.index.ntotal} vectors.")
            except Exception as e:
                logger.error(f"Error saving FAISS index: {e}")

    def add_embeddings(
        self,
        embeddings: np.ndarray,
        chunk_ids: List[int],
        document_id: int,
    ) -> None:
        """
        Add embeddings to the FAISS index with metadata mapping.

        Args:
            embeddings: Numpy array of shape (n, dimension), L2-normalized.
            chunk_ids: List of database chunk IDs.
            document_id: The document these chunks belong to.
        """
        with self._lock:
            if self.index is None:
                self._initialize_index()

            # Normalize vectors for cosine similarity via inner product
            faiss.normalize_L2(embeddings)

            # Add to index
            self.index.add(embeddings)  # type: ignore

            # Update mapping
            for i, chunk_id in enumerate(chunk_ids):
                faiss_id = self._next_id + i
                self.id_mapping[faiss_id] = {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                }
            self._next_id += len(chunk_ids)

            logger.info(
                f"Added {len(chunk_ids)} embeddings for document {document_id}. "
                f"Total vectors: {self.index.ntotal}"
            )

            # Save after adding
            self._save_unlocked()

    def _save_unlocked(self) -> None:
        """Save index without acquiring lock (caller must hold lock)."""
        if self.index is None:
            return
        try:
            os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
            faiss.write_index(self.index, self._index_file)
            with open(self._mapping_file, "w") as f:
                json.dump(self.id_mapping, f)
        except Exception as e:
            logger.error(f"Error saving FAISS index: {e}")

    def search(
        self,
        query_embedding: np.ndarray,
        document_id: int,
        top_k: int = 5,
    ) -> List[Tuple[int, float]]:
        """
        Search for the most similar chunks for a given document.

        Args:
            query_embedding: Normalized query vector of shape (1, dimension).
            document_id: Filter results to this document only.
            top_k: Number of results to return.

        Returns:
            List of (chunk_id, similarity_score) tuples.
        """
        with self._lock:
            if self.index is None or self.index.ntotal == 0:
                logger.warning("FAISS index is empty. No results.")
                return []

            # Normalize query
            faiss.normalize_L2(query_embedding)

            # Search with a larger k to account for filtering
            search_k = min(top_k * 10, self.index.ntotal)
            distances, indices = self.index.search(query_embedding, search_k)  # type: ignore

            results: List[Tuple[int, float]] = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    continue
                mapping = self.id_mapping.get(idx)
                if mapping and mapping["document_id"] == document_id:
                    results.append((mapping["chunk_id"], float(dist)))
                    if len(results) >= top_k:
                        break

            logger.info(
                f"Search returned {len(results)} results for document {document_id}"
            )
            return results


# Global singleton instance
vector_store_manager = VectorStoreManager()
