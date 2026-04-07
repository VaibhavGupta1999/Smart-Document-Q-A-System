"""
Retrieval Agent

Handles the "find relevant stuff" part of the pipeline.
Wraps the embedding service and FAISS vector store to provide
a simple search interface. Includes the re-ranking step.
"""

import logging
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class RetrievalAgent:
    """
    Agent responsible for finding relevant document chunks.

    Under the hood it uses sentence-transformers for query embedding
    and FAISS for similarity search, then re-ranks results with
    keyword overlap. But callers don't need to know any of that.
    """

    def __init__(self, db: Session):
        self.db = db
        logger.debug("[RetrievalAgent] Initialized")

    def search(
        self,
        query: str,
        document_id: int,
        top_k: int = settings.TOP_K,
    ) -> List[Tuple[Chunk, float]]:
        """
        Find the most relevant chunks for a question within a document.

        Returns list of (chunk, relevance_score) tuples sorted by relevance.
        Empty list if nothing relevant is found.
        """
        logger.info(
            f"[RetrievalAgent] Searching for relevant chunks "
            f"(doc={document_id}, top_k={top_k})"
        )

        results = RetrievalService.retrieve_relevant_chunks(
            db=self.db,
            query=query,
            document_id=document_id,
            top_k=top_k,
        )

        if not results:
            logger.warning(
                f"[RetrievalAgent] No relevant chunks found for doc {document_id}"
            )
        else:
            logger.info(
                f"[RetrievalAgent] Retrieved {len(results)} chunks "
                f"(best score: {results[0][1]:.4f})"
            )

        return results

    def has_relevant_context(
        self,
        query: str,
        document_id: int,
        min_score: float = 0.1,
    ) -> bool:
        """
        Quick check — does the document have anything relevant to say
        about this query? Uses a low threshold to be permissive.
        """
        results = self.search(query, document_id, top_k=1)
        if not results:
            return False
        _, score = results[0]
        return score >= min_score
