"""
Answering Agent

The "brains" of the operation. Takes relevant chunks and
conversation context, then uses the LLM to generate an answer.
Wraps the existing LLM service so other components don't
need to deal with prompt engineering details.
"""

import logging
from typing import List, Optional, Tuple

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.message import Message
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class AnsweringAgent:
    """
    Agent responsible for generating answers using the LLM.

    Delegates to LLMService for the actual API call, but handles
    edge cases and logging at the agent level.
    """

    def __init__(self):
        logger.debug("[AnsweringAgent] Initialized")

    def generate(
        self,
        question: str,
        relevant_chunks: List[Tuple[Chunk, float]],
        previous_messages: Optional[List[Message]] = None,
    ) -> str:
        """
        Generate an answer to the user's question.

        If there are no relevant chunks, we don't even bother calling
        the LLM — just return a "no context" message. This saves
        API calls and avoids hallucination.
        """
        if not relevant_chunks:
            logger.warning("[AnsweringAgent] No chunks provided, skipping LLM call")
            return "No relevant context found in the document to answer your question."

        logger.info(
            f"[AnsweringAgent] Generating answer with {len(relevant_chunks)} chunks"
        )

        # let the LLM service handle prompt construction and API call
        answer = LLMService.generate_answer(
            question=question,
            relevant_chunks=relevant_chunks,
            previous_messages=previous_messages,
        )

        # basic sanity check on the response
        if not answer or len(answer.strip()) == 0:
            logger.warning("[AnsweringAgent] Got empty response from LLM")
            return (
                "I received an empty response from the language model. "
                "Please try rephrasing your question."
            )

        logger.info(
            f"[AnsweringAgent] Generated response ({len(answer)} chars)"
        )
        return answer

    @property
    def model_name(self) -> str:
        """Which model is being used — useful for response metadata."""
        return settings.LLM_MODEL
