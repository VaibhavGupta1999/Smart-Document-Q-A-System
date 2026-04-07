"""
Retrieval Service - Finds relevant document chunks for a query.

Combines vector search with optional re-ranking to find the most
relevant context for answering user questions.
"""

import logging
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.vector_store import vector_store_manager
from app.models.chunk import Chunk
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving relevant chunks using vector similarity search."""

    @staticmethod
    def retrieve_relevant_chunks(
        db: Session,
        query: str,
        document_id: int,
        top_k: int = settings.TOP_K,
    ) -> List[Tuple[Chunk, float]]:
        """
        Retrieve the most relevant chunks for a query from a specific document.

        Performs:
        1. Generate query embedding
        2. FAISS similarity search (filtered by document_id)
        3. Fetch full chunk content from database
        4. Re-rank by relevance score

        Args:
            db: Database session.
            query: User's question.
            document_id: Document to search within.
            top_k: Number of chunks to return.

        Returns:
            List of (Chunk, similarity_score) tuples, sorted by relevance.
        """
        # 1. Generate query embedding
        query_embedding = EmbeddingService.generate_query_embedding(query)

        # 2. Search FAISS index
        search_results = vector_store_manager.search(
            query_embedding=query_embedding,
            document_id=document_id,
            top_k=top_k,
        )

        if not search_results:
            logger.warning(f"No relevant chunks found for document {document_id}")
            return []

        # 3. Fetch chunks from database
        chunk_ids = [chunk_id for chunk_id, _ in search_results]
        score_map = {chunk_id: score for chunk_id, score in search_results}

        chunks = db.query(Chunk).filter(
            Chunk.id.in_(chunk_ids),
            Chunk.document_id == document_id,
        ).all()

        # 4. Pair with scores and sort by relevance
        results: List[Tuple[Chunk, float]] = []
        for chunk in chunks:
            score = score_map.get(chunk.id, 0.0)
            results.append((chunk, score))

        # Sort by score descending (higher = more relevant)
        results.sort(key=lambda x: x[1], reverse=True)

        # Re-ranking step: boost chunks that have higher keyword overlap
        results = RetrievalService._rerank(query, results)

        logger.info(
            f"Retrieved {len(results)} relevant chunks for document {document_id}"
        )
        return results

    @staticmethod
    def _rerank(
        query: str,
        chunks_with_scores: List[Tuple[Chunk, float]],
    ) -> List[Tuple[Chunk, float]]:
        """
        Simple re-ranking step that combines vector similarity score
        with keyword overlap for better relevance.

        Uses a weighted combination:
        - 80% vector similarity score
        - 20% keyword overlap score
        """
        if not chunks_with_scores:
            return chunks_with_scores

        query_terms = set(query.lower().split())

        reranked = []
        for chunk, vector_score in chunks_with_scores:
            # Calculate keyword overlap
            chunk_terms = set(chunk.content.lower().split())
            if len(query_terms) > 0:
                overlap = len(query_terms & chunk_terms) / len(query_terms)
            else:
                overlap = 0.0

            # Weighted combination
            combined_score = (0.8 * vector_score) + (0.2 * overlap)
            reranked.append((chunk, combined_score))

        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked
