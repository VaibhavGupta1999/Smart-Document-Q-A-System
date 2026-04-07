"""
Pydantic schemas for document-related API requests and responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response schema after uploading a document."""
    id: int
    filename: str
    status: str
    message: str = "Document uploaded successfully. Processing will begin shortly."

    class Config:
        from_attributes = True


class DocumentStatusResponse(BaseModel):
    """Response schema for checking document processing status."""
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    chunk_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Response schema for listing documents."""
    documents: list[DocumentStatusResponse]
    total: int
