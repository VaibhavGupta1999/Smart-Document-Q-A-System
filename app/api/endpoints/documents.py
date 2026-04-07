"""
Document Endpoints — Upload documents and check processing status.

Uses the DocumentProcessingAgent instead of calling services directly.
Routes stay exactly the same, just the wiring changed.

POST /documents/upload       — upload a PDF or DOCX file
GET  /documents/{id}/status  — check processing status
GET  /documents/             — list all documents
DELETE /documents/{id}       — delete a document
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.agents.document_agent import DocumentProcessingAgent, process_document_background
from app.core.database import get_db
from app.schemas.document import (
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {"pdf", "docx"}


def _get_file_extension(filename: str) -> str:
    """Extract and validate file extension."""
    if "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have an extension (.pdf or .docx)",
        )
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: .{ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    return ext


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF or DOCX file to upload"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a document for async processing."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    file_type = _get_file_extension(file.filename)
    file_content = await file.read()

    if len(file_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(file_content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 50MB limit",
        )

    agent = DocumentProcessingAgent(db)
    document = agent.upload_and_process(
        original_filename=file.filename,
        file_content=file_content,
        file_type=file_type,
    )
    
    if background_tasks:
        background_tasks.add_task(process_document_background, document.id)

    return DocumentUploadResponse(
        id=document.id,
        filename=document.original_filename,
        status=document.status if isinstance(document.status, str) else document.status.value,
        message="Document uploaded successfully. Processing will begin shortly.",
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Get document status",
)
async def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
) -> DocumentStatusResponse:
    """Check the current processing status of a document."""
    agent = DocumentProcessingAgent(db)
    document = agent.get_status(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    return DocumentStatusResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status if isinstance(document.status, str) else document.status.value,
        error_message=document.error_message,
        chunk_count=document.chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List all documents",
)
async def list_documents(
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """Get a list of all uploaded documents."""
    agent = DocumentProcessingAgent(db)
    documents = agent.get_all_documents()

    doc_responses = [
        DocumentStatusResponse(
            id=doc.id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status if isinstance(doc.status, str) else doc.status.value,
            error_message=doc.error_message,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in documents
    ]
    return DocumentListResponse(documents=doc_responses, total=len(doc_responses))


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a document and all associated data."""
    agent = DocumentProcessingAgent(db)
    success = agent.delete(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
