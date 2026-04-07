"""
Pydantic schemas for conversation-related API responses.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Individual message in a conversation."""
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Full conversation with all messages."""
    id: int
    document_id: int
    messages: List[MessageResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """List of conversations."""
    conversations: List[ConversationResponse]
    total: int
