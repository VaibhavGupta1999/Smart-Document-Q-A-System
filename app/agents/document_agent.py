"""
Document Processing Agent

Handles document lifecycle: upload, processing, status, cleanup.
Processes documents synchronously — no Celery/Redis needed.
"""

import logging
import traceback
from typing import Optional, List

import numpy as np
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.chunk import Chunk
from app.core.database import SessionLocal
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
from app.core.vector_store import vector_store_manager
from app.utils.text_processing import TextProcessor

logger = logging.getLogger(__name__)

def process_document_background(document_id: int):
    """
    Background worker that fetches its own independent DB Session.
    This prevents SQLAlchemy 'Instance is not bound to a Session' errors 
    when running via FastAPI BackgroundTasks after the parent route returns.
    """
    db = SessionLocal()
    try:
        agent = DocumentProcessingAgent(db)
        document = agent.get_status(document_id)
        if document:
            agent._process_document(document)
    except Exception as e:
        logger.error(f"Failed to initialize background processing for doc {document_id}: {e}")
    finally:
        db.close()


class DocumentProcessingAgent:
    """
    Agent responsible for document lifecycle management.

    Processes documents synchronously inline — simpler than
    Celery but fine for an assignment / small-scale use.
    """

    def __init__(self, db: Session):
        self.db = db
        logger.debug("[DocumentProcessingAgent] Initialized")

    def upload_and_process(
        self,
        original_filename: str,
        file_content: bytes,
        file_type: str,
    ) -> Document:
        """
        Handle a new document upload: save to disk, create db record,
        and process it synchronously (extract → chunk → embed → index).

        Returns the document record with final status (READY or FAILED).
        """
        logger.info(f"[DocumentProcessingAgent] Uploading: {original_filename}")

        # create the record + save file
        document = DocumentService.create_document(
            db=self.db,
            original_filename=original_filename,
            file_content=file_content,
            file_type=file_type,
        )

        # We no longer process synchronously here. We return the document
        # and let the endpoint queue up the background task to fulfill the async requisite.
        return document

    def _process_document(self, document: Document) -> None:
        """Run the full processing pipeline synchronously."""
        try:
            document.status = DocumentStatus.PROCESSING
            self.db.commit()

            # Step 1: Extract text
            logger.info(f"[Agent] Step 1: Extracting text from {document.file_type}")
            raw_text = TextProcessor.extract_text(document.file_path, document.file_type)

            if not raw_text or len(raw_text.strip()) < 10:
                raise ValueError("Extracted text is empty or too short")

            # Step 2: Clean text
            logger.info("[Agent] Step 2: Cleaning text")
            cleaned_text = TextProcessor.clean_text(raw_text)

            # Step 3: Chunk text
            logger.info("[Agent] Step 3: Chunking text")
            text_chunks = TextProcessor.chunk_text(cleaned_text)

            if not text_chunks:
                raise ValueError("No chunks generated from document text")

            logger.info(f"[Agent] Generated {len(text_chunks)} chunks")

            # Step 4: Save chunks to database
            logger.info("[Agent] Step 4: Saving chunks to DB")
            db_chunks: List[Chunk] = []
            for i, chunk_text in enumerate(text_chunks):
                chunk = Chunk(
                    document_id=document.id,
                    content=chunk_text,
                    chunk_index=i,
                    token_count=TextProcessor.count_tokens(chunk_text),
                )
                self.db.add(chunk)
                db_chunks.append(chunk)

            self.db.commit()
            for chunk in db_chunks:
                self.db.refresh(chunk)

            chunk_ids = [chunk.id for chunk in db_chunks]

            # Step 5: Generate embeddings
            logger.info("[Agent] Step 5: Generating embeddings")
            chunk_texts = [chunk.content for chunk in db_chunks]
            embeddings = EmbeddingService.generate_embeddings(chunk_texts)

            # Step 6: Add to FAISS
            logger.info("[Agent] Step 6: Adding to FAISS index")
            vector_store_manager.add_embeddings(
                embeddings=embeddings,
                chunk_ids=chunk_ids,
                document_id=document.id,
            )

            # Done — mark as READY
            document.status = DocumentStatus.READY
            document.chunk_count = len(db_chunks)
            self.db.commit()

            logger.info(
                f"[Agent] Document {document.id} processed! "
                f"{len(db_chunks)} chunks indexed."
            )

        except Exception as e:
            logger.error(
                f"[Agent] Error processing document {document.id}: {e}\n"
                f"{traceback.format_exc()}"
            )
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)[:500]
            self.db.commit()

    def get_status(self, document_id: int) -> Optional[Document]:
        """Check where a document is in the pipeline."""
        return DocumentService.get_document(self.db, document_id)

    def get_all_documents(self) -> List[Document]:
        """Get every document we know about."""
        return DocumentService.get_all_documents(self.db)

    def is_ready(self, document_id: int) -> bool:
        """Quick check — is this document ready for Q&A?"""
        doc = self.get_status(document_id)
        if not doc:
            return False
        return doc.status == DocumentStatus.READY

    def delete(self, document_id: int) -> bool:
        """Remove a document and all its data."""
        logger.info(f"[DocumentProcessingAgent] Deleting doc {document_id}")
        return DocumentService.delete_document(self.db, document_id)
