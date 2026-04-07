"""
Questions Endpoint — Ask questions about uploaded documents.

This is the key refactored endpoint. Instead of calling services
directly, it goes through the QAOrchestrator which coordinates
the agents internally.

POST /questions/ask — ask a question about a document
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.orchestrator.qa_orchestrator import QAOrchestrator
from app.schemas.question import QuestionRequest, QuestionResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/ask",
    response_model=QuestionResponse,
    summary="Ask a question about a document",
    description="Submit a question about a specific document. Optionally continue a conversation.",
)
def ask_question(
    request: QuestionRequest,
    db: Session = Depends(get_db),
) -> QuestionResponse:
    """
    Ask a question about an uploaded document.

    OLD approach: API → service → service → service (pipeline)
    NEW approach: API → orchestrator → agents (coordinated)

    The orchestrator handles all the agent coordination, error
    handling, and fallback logic internally.
    """
    logger.info(
        f"Received question for doc {request.document_id}: "
        f"'{request.question[:60]}...'"
    )

    # just hand it off to the orchestrator — it handles everything
    orchestrator = QAOrchestrator(db)
    response = orchestrator.handle_query(
        question=request.question,
        document_id=request.document_id,
        conversation_id=request.conversation_id,
    )

    return response
