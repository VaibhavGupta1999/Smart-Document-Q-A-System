"""
Document Service - Handles document CRUD operations.

Manages document creation, status updates, and metadata retrieval.
"""

import logging
import os
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentStatus

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for managing document records and file storage."""

    @staticmethod
    def create_document(
        db: Session,
        original_filename: str,
        file_content: bytes,
        file_type: str,
    ) -> Document:
        """
        Create a new document record and save the file to disk.

        Args:
            db: Database session.
            original_filename: Original name of the uploaded file.
            file_content: Raw file bytes.
            file_type: File extension (pdf, docx).

        Returns:
            The created Document model instance.
        """
        # Generate unique filename
        unique_name = f"{uuid.uuid4().hex}_{original_filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_name)

        # Ensure upload directory exists
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"Saved file to {file_path} ({len(file_content)} bytes)")

        # Create database record
        document = Document(
            filename=unique_name,
            original_filename=original_filename,
            file_path=file_path,
            file_size=len(file_content),
            file_type=file_type,
            status=DocumentStatus.UPLOADING,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        logger.info(f"Created document record: id={document.id}, filename={original_filename}")
        return document

    @staticmethod
    def get_document(db: Session, document_id: int) -> Optional[Document]:
        """Get a document by ID."""
        return db.query(Document).filter(Document.id == document_id).first()

    @staticmethod
    def get_all_documents(db: Session) -> List[Document]:
        """Get all documents ordered by creation date."""
        return db.query(Document).order_by(Document.created_at.desc()).all()

    @staticmethod
    def update_status(
        db: Session,
        document_id: int,
        status: DocumentStatus,
        error_message: Optional[str] = None,
        chunk_count: int = 0,
    ) -> Optional[Document]:
        """
        Update the processing status of a document.

        Args:
            db: Database session.
            document_id: Document to update.
            status: New status value.
            error_message: Optional error details for FAILED status.
            chunk_count: Number of chunks created.

        Returns:
            Updated Document or None if not found.
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = status
            if error_message:
                document.error_message = error_message
            if chunk_count:
                document.chunk_count = chunk_count
            db.commit()
            db.refresh(document)
            logger.info(f"Document {document_id} status updated to {status.value}")
        return document

    @staticmethod
    def delete_document(db: Session, document_id: int) -> bool:
        """Delete a document and its file from disk."""
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return False

        # Delete file from disk
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
            logger.info(f"Deleted file: {document.file_path}")

        db.delete(document)
        db.commit()
        logger.info(f"Deleted document record: id={document_id}")
        return True
