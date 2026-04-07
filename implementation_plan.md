# Smart Document Q&A System

This document outlines the implementation plan for the Smart Document Q&A backend system using FastAPI, PostgreSQL, Celery, Redis, FAISS, Sentence Transformers, and OpenAI.

## Goal Description

To build a production-grade backend system for B2B SaaS that allows users to upload PDF/DOCX documents, processes them asynchronously by extracting text, chunking, and generating embeddings, and enables users to ask follow-up questions over those documents using an LLM configured with RAG (Retrieval-Augmented Generation).

## User Review Required

> [!IMPORTANT]
> - Do you have any specific preferences for the base Docker image (e.g., Python 3.10 vs 3.11)? I will use `python:3.11-slim` by default.
> - The prompt currently assumes a single user context without full JWT auth. Let me know if you need basic user management, otherwise I will omit it for simplicity.
> - I will set up the FAISS index to be a single flat file vector store which is loaded into memory on process start (in both FastAPI and Celery worker).
> - Sentence transformers can be heavy for Docker building. We'll use a lightweight model like `all-MiniLM-L6-v2`.

## Proposed Changes

We will create a robust, modular project structure in `f:\careerflow\hiring hub assigment` without monolithic files. 

### Infrastructure & Config
#### [NEW] `docker-compose.yml`
Setup for FastAPI API, PostgreSQL, Redis, and a Celery Worker.
#### [NEW] `Dockerfile`
Multi-stage build for API and Worker.
#### [NEW] `requirements.txt`
All required dependencies (FastAPI, SQLAlchemy, Celery, Redis, FAISS, Sentence-Transformers, OpenAI, PyMuPDF, etc.)
#### [NEW] `.env.example`
Example environment variables (DB, Redis, OpenAI).

---

### Core & Setup
#### [NEW] `app/main.py`
FastAPI app initialization, router inclusion, and FAISS index startup logic.
#### [NEW] `app/core/config.py`
Pydantic Settings for env vars.
#### [NEW] `app/core/database.py`
SQLAlchemy synchronous engine `psycopg2` setup (synchronous used for both FastAPI and Celery for simplicity as IO here is fast enough and RAG is compute-heavy).
#### [NEW] `app/core/celery_app.py`
Celery initialization using Redis as broker and backend.
#### [NEW] `app/core/vector_store.py`
Singleton/manager for the FAISS index to do similarity search and additions, persistent to disk.

---

### Database Models
#### [NEW] `app/models/document.py`
Model for `documents` table (`id`, `filename`, `status`, `created_at`).
#### [NEW] `app/models/chunk.py`
Model for `chunks` table (`id`, `document_id`, `content`).
#### [NEW] `app/models/conversation.py`
Model for `conversations` table (`id`, `created_at`).
#### [NEW] `app/models/message.py`
Model for `messages` table (`id`, `conversation_id`, `role`, `content`, `created_at`).

---

### Pydantic Schemas
#### [NEW] `app/schemas/document.py`
Schemas for upload response, status check.
#### [NEW] `app/schemas/question.py`
Schemas for asking questions (question, doc_id, optional conv_id) and LLM response.
#### [NEW] `app/schemas/conversation.py`
Schemas for viewing conversation history.

---

### Business Logic (Services)
#### [NEW] `app/services/document_service.py`
Handles creating DB records for documents and fetching statuses.
#### [NEW] `app/services/embedding_service.py`
Handles `sentence-transformers` vector generation.
#### [NEW] `app/services/retrieval_service.py`
Given a query and document_id, vectorizes query and queries FAISS for top-k. Returns chunks.
#### [NEW] `app/services/llm_service.py`
Calls OpenAI API using context (from retrieval), previous conversation history, and user's query.

---

### Background Workers
#### [NEW] `app/workers/tasks.py`
Celery task `process_document_task(doc_id: int, file_path: str)`. Extracts text (PDF/DOCX), chunks text using chunk size 500-800, calls `embedding_service`, updates FAISS, saves chunks to Postgres, marks doc as READY/FAILED.

---

### API Endpoints
#### [NEW] `app/api/router.py`
Combines sub-routers.
#### [NEW] `app/api/endpoints/documents.py`
`POST /documents/upload`, `GET /documents/{id}/status`.
#### [NEW] `app/api/endpoints/questions.py`
`POST /questions/ask`.
#### [NEW] `app/api/endpoints/conversations.py`
`GET /conversations/{id}`.

---

### Utils
#### [NEW] `app/utils/text_processing.py`
PDF/DOCX extraction and smart overlapping chunking logic.

---

### Migrations
#### [NEW] `alembic.ini` & `alembic/` folder
For DB schema migrations.

---

### Sample Documents
#### [NEW] `sample_docs/`
3 sample PDFs/DOCXs.

---

### Documentation
#### [NEW] `README.md`
Detailed setup instructions, API usage, architecture decisions.

## Open Questions

- We will proceed with generating all files and then spinning up Docker. Do you have an OpenAI API Key ready to plonk into `.env` when we test? 

## Verification Plan

### Automated Tests
- I will run `docker-compose up -build` to ensure the entire stack spins up.
- Use `curl` to upload a provided sample document, verify status goes READY.
- Use `curl` to ask a question and confirm an accurate LLM response.

### Manual Verification
- Will verify chunks exist in PostgreSQL.
- Will verify FAISS index file is populated and successfully saves to disk.
