"""
Conversation Agent

Manages conversation state — creating new conversations,
loading history for follow-ups, and persisting messages.
This keeps the orchestrator clean by handling all the
conversation bookkeeping in one place.
"""

import json
import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message, MessageRole

logger = logging.getLogger(__name__)


class ConversationAgent:
    """
    Agent responsible for conversation lifecycle and message persistence.

    Handles creating conversations, fetching history for context,
    and saving new Q&A exchanges.
    """

    def __init__(self, db: Session):
        self.db = db
        logger.debug("[ConversationAgent] Initialized")

    def get_or_create_conversation(
        self,
        document_id: int,
        conversation_id: Optional[int] = None,
    ) -> Tuple[Conversation, List[Message]]:
        """
        Either load an existing conversation or spin up a new one.

        Returns the conversation object and any previous messages
        (empty list for new conversations).
        """
        if conversation_id:
            conversation = (
                self.db.query(Conversation)
                .filter(Conversation.id == conversation_id)
                .first()
            )

            if conversation is None:
                logger.warning(
                    f"[ConversationAgent] Conversation {conversation_id} not found, "
                    f"creating new one"
                )
                return self._create_new(document_id)

            # make sure the conversation actually belongs to this document
            if conversation.document_id != document_id:
                logger.error(
                    f"[ConversationAgent] Conversation {conversation_id} belongs to "
                    f"doc {conversation.document_id}, not {document_id}"
                )
                raise ValueError(
                    "Conversation does not belong to the specified document"
                )

            previous_messages = list(conversation.messages)
            logger.info(
                f"[ConversationAgent] Loaded conversation {conversation_id} "
                f"with {len(previous_messages)} messages"
            )
            return conversation, previous_messages

        return self._create_new(document_id)

    def _create_new(self, document_id: int) -> Tuple[Conversation, List[Message]]:
        """Create a fresh conversation."""
        conversation = Conversation(document_id=document_id)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        logger.info(
            f"[ConversationAgent] Created new conversation {conversation.id} "
            f"for doc {document_id}"
        )
        return conversation, []

    def save_exchange(
        self,
        conversation_id: int,
        question: str,
        answer: str,
        chunk_ids_used: Optional[List[int]] = None,
    ) -> None:
        """
        Save a Q&A exchange (user question + assistant answer) to the db.
        Also records which chunks were used for the answer.
        """
        # save the user's question
        user_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=question,
        )
        self.db.add(user_msg)

        # save the assistant's answer
        assistant_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=answer,
            chunks_used=json.dumps(chunk_ids_used) if chunk_ids_used else None,
        )
        self.db.add(assistant_msg)

        self.db.commit()
        logger.info(
            f"[ConversationAgent] Saved exchange to conversation {conversation_id}"
        )

    def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        """Load a conversation by ID."""
        return (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

    def get_all_conversations(self) -> List[Conversation]:
        """Get all conversations, newest first."""
        return (
            self.db.query(Conversation)
            .order_by(Conversation.created_at.desc())
            .all()
        )
