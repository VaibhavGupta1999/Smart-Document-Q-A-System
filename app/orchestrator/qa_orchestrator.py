"""
Q&A Orchestrator — the central coordinator.

This is the brain of the agent-based architecture. Instead of API
endpoints directly calling services, they call the orchestrator,
which coordinates the agents in the right order:

    query → RetrievalAgent → ConversationAgent → AnsweringAgent → response

All the failure handling and fallback logic lives here too, keeping
the individual agents focused on their one job.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.agents.answering_agent import AnsweringAgent
from app.agents.conversation_agent import ConversationAgent
from app.agents.document_agent import DocumentProcessingAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.schemas.question import ChunkReference, QuestionResponse

logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    """Internal result from the orchestrator pipeline."""
    answer: str
    conversation_id: int
    document_id: int
    question: str
    source_chunks: List[Tuple[Chunk, float]]
    model_used: str


class QAOrchestrator:
    """
    Central orchestrator that coordinates all agents for Q&A.

    Typical flow:
    1. Validate document (via DocumentProcessingAgent)
    2. Retrieve relevant chunks (via RetrievalAgent)
    3. Load conversation context (via ConversationAgent)
    4. Generate answer (via AnsweringAgent)
    5. Save the exchange (via ConversationAgent)

    If anything goes wrong at any step, we handle it gracefully
    instead of letting exceptions bubble up to the user.
    """

    def __init__(self, db: Session):
        self.db = db
        self.doc_agent = DocumentProcessingAgent(db)
        self.retrieval_agent = RetrievalAgent(db)
        self.conversation_agent = ConversationAgent(db)
        self.answering_agent = AnsweringAgent()
        logger.debug("[Orchestrator] All agents initialized")

    def handle_query(
        self,
        question: str,
        document_id: int,
        conversation_id: Optional[int] = None,
    ) -> QuestionResponse:
        """
        Main entry point for handling a user question.

        This is what the API layer calls. Everything else is internal.
        """
        logger.info(
            f"[Orchestrator] Handling query for doc {document_id}: "
            f"'{question[:80]}...'"
        )

        # ── Step 1: Validate the document ──
        logger.info("[Orchestrator] Step 1: Validating document")
        document = self.doc_agent.get_status(document_id)

        if document is None:
            logger.error(f"[Orchestrator] Document {document_id} not found")
            return self._error_response(
                question, document_id,
                "Document not found. Please check the document ID."
            )

        if document.status != DocumentStatus.READY:
            logger.warning(
                f"[Orchestrator] Document {document_id} not ready "
                f"(status: {document.status.value})"
            )
            return self._error_response(
                question, document_id,
                f"Document is not ready for questions. "
                f"Current status: {document.status.value}. "
                f"Please wait for processing to complete."
            )

        # ── Step 2: Retrieve relevant chunks ──
        logger.info("[Orchestrator] Step 2: Calling RetrievalAgent")
        try:
            relevant_chunks = self.retrieval_agent.search(
                query=question,
                document_id=document_id,
                top_k=settings.TOP_K,
            )
        except Exception as e:
            logger.error(f"[Orchestrator] RetrievalAgent failed: {e}")
            return self._error_response(
                question, document_id,
                "Failed to search the document. Please try again."
            )

        if not relevant_chunks:
            logger.info("[Orchestrator] No relevant chunks found")
            # still save the conversation so the user sees it in history
            conv, _ = self.conversation_agent.get_or_create_conversation(
                document_id, conversation_id
            )
            no_context_msg = (
                "No relevant context found in the document to answer "
                "your question. Try rephrasing or asking about a different topic."
            )
            self.conversation_agent.save_exchange(
                conv.id, question, no_context_msg
            )
            return QuestionResponse(
                answer=no_context_msg,
                conversation_id=conv.id,
                document_id=document_id,
                question=question,
                source_chunks=[],
                model_used=self.answering_agent.model_name,
            )

        logger.info(
            f"[Orchestrator] RetrievalAgent returned {len(relevant_chunks)} chunks"
        )

        # ── Step 3: Load conversation context ──
        logger.info("[Orchestrator] Step 3: Calling ConversationAgent")
        try:
            conversation, previous_messages = (
                self.conversation_agent.get_or_create_conversation(
                    document_id, conversation_id
                )
            )
        except ValueError as e:
            # conversation doesn't belong to this document
            return self._error_response(question, document_id, str(e))
        except Exception as e:
            logger.error(f"[Orchestrator] ConversationAgent failed: {e}")
            # try without conversation context
            conversation, previous_messages = (
                self.conversation_agent.get_or_create_conversation(document_id)
            )

        # ── Step 4: Generate answer ──
        logger.info("[Orchestrator] Step 4: Calling AnsweringAgent")
        try:
            answer = self.answering_agent.generate(
                question=question,
                relevant_chunks=relevant_chunks,
                previous_messages=previous_messages if previous_messages else None,
            )
        except Exception as e:
            logger.error(f"[Orchestrator] AnsweringAgent failed: {e}")
            answer = (
                "I apologize, but I couldn't generate an answer right now. "
                "The relevant document sections are shown below in the source "
                "chunks for your reference."
            )

        # ── Step 5: Save the exchange ──
        logger.info("[Orchestrator] Step 5: Saving exchange")
        chunk_ids_used = [chunk.id for chunk, _ in relevant_chunks]
        try:
            self.conversation_agent.save_exchange(
                conversation.id, question, answer, chunk_ids_used
            )
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to save exchange: {e}")
            # not a dealbreaker — the answer is still valid

        # ── Build response ──
        source_chunks = [
            ChunkReference(
                chunk_id=chunk.id,
                content=(
                    chunk.content[:300] + "..."
                    if len(chunk.content) > 300
                    else chunk.content
                ),
                relevance_score=round(score, 4),
            )
            for chunk, score in relevant_chunks
        ]

        logger.info(
            f"[Orchestrator] Done. Conversation {conversation.id}, "
            f"{len(source_chunks)} sources used."
        )

        return QuestionResponse(
            answer=answer,
            conversation_id=conversation.id,
            document_id=document_id,
            question=question,
            source_chunks=source_chunks,
            model_used=self.answering_agent.model_name,
        )

    def _error_response(
        self, question: str, document_id: int, error_msg: str,
    ) -> QuestionResponse:
        """Build a QuestionResponse for error cases."""
        return QuestionResponse(
            answer=error_msg,
            conversation_id=0,
            document_id=document_id,
            question=question,
            source_chunks=[],
            model_used=self.answering_agent.model_name,
        )
