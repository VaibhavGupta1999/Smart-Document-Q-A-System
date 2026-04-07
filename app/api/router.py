"""
API Router - Combines all endpoint sub-routers.

Central router that aggregates all API endpoints under
their respective prefixes.
"""

from fastapi import APIRouter

from app.api.endpoints import documents, questions, conversations

api_router = APIRouter()

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"],
)
api_router.include_router(
    questions.router,
    prefix="/questions",
    tags=["Questions"],
)
api_router.include_router(
    conversations.router,
    prefix="/conversations",
    tags=["Conversations"],
)
