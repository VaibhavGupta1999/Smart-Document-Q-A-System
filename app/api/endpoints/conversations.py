"""
Conversations Endpoint — View conversation history.

Uses the ConversationAgent for data access.

GET /conversations/{id} — get a conversation with all messages
GET /conversations/     — list all conversations
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.conversation_agent import ConversationAgent
from app.core.database import get_db
from app.schemas.conversation import (
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation history",
)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> ConversationResponse:
    """Retrieve a conversation with all its messages."""
    agent = ConversationAgent(db)
    conversation = agent.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found",
        )

    messages = [
        MessageResponse(
            id=msg.id,
            role=msg.role.value if hasattr(msg.role, 'value') else msg.role,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg in conversation.messages
    ]

    return ConversationResponse(
        id=conversation.id,
        document_id=conversation.document_id,
        messages=messages,
        created_at=conversation.created_at,
    )


@router.get(
    "/",
    response_model=ConversationListResponse,
    summary="List all conversations",
)
async def list_conversations(
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    """Get a list of all conversations."""
    agent = ConversationAgent(db)
    conversations = agent.get_all_conversations()

    conv_responses = []
    for conv in conversations:
        messages = [
            MessageResponse(
                id=msg.id,
                role=msg.role.value if hasattr(msg.role, 'value') else msg.role,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in conv.messages
        ]
        conv_responses.append(
            ConversationResponse(
                id=conv.id,
                document_id=conv.document_id,
                messages=messages,
                created_at=conv.created_at,
            )
        )

    return ConversationListResponse(
        conversations=conv_responses,
        total=len(conv_responses),
    )
