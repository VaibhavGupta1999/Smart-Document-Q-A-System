"""
Pydantic schemas for question-answering API requests and responses.
"""

from typing import Optional, List

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    """Request schema for asking a question."""
    question: str = Field(..., min_length=1, max_length=2000, description="The question to ask about the document")
    document_id: int = Field(..., gt=0, description="ID of the document to query")
    conversation_id: Optional[int] = Field(None, description="Optional conversation ID for follow-up questions")


class ChunkReference(BaseModel):
    """Reference to a source chunk used in the answer."""
    chunk_id: int
    content: str
    relevance_score: float


class QuestionResponse(BaseModel):
    """Response schema for a question answer."""
    answer: str
    conversation_id: int
    document_id: int
    question: str
    source_chunks: List[ChunkReference] = []
    model_used: str = ""
