# DocuMind AI — Smart Document Q&A System

A production-grade, agent-based document question-answering system built with **FastAPI, SQLite, FAISS, Sentence Transformers, and Groq (LLaMA 4 Scout)**.

Upload PDF/DOCX documents and ask natural-language questions about their content. The system extracts text, chunks it intelligently, generates embeddings, and uses RAG (Retrieval-Augmented Generation) to provide accurate, grounded answers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (HTML/CSS/JS)                   │
│                     Premium dark-mode chat UI                   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼────────────────────────────────────┐
│                      FastAPI (API Layer)                        │
│                  /api/documents  /api/questions                 │
└──────┬──────────────────┬──────────────────┬────────────────────┘
       │                  │                  │
┌──────▼──────┐   ┌───────▼───────┐   ┌──────▼──────┐
│  Document   │   │      Q&A      │   │ Conversation│
│ Processing  │   │ Orchestrator  │   │    Agent    │
│   Agent     │   │               │   │             │
└──────┬──────┘   └───┬───┬───┬───┘   └─────────────┘
       │              │   │   │
       │         ┌────┘   │   └────┐
  [Background    │        │        │
    Tasks]       │        │        │
                 │        │        │
  ┌────┴────┐ ┌──▼───┐ ┌──▼──┐ ┌──▼──────┐
  │ Text    │ │Retri-│ │Conv-│ │Answering│
  │Processor│ │eval  │ │ersa-│ │  Agent  │
  │ Embed   │ │Agent │ │tion │ │ (Groq)  │
  └────┬────┘ └──┬───┘ │Agent│ └─────────┘
       │         │     └─────┘
  ┌────▼────┐ ┌──▼───┐
  │ SQLite  │ │FAISS │
  │ Database│ │Index │
  └─────────┘ └──────┘
```

### Agent-Based Architecture

The system uses a **multi-agent architecture** with a central orchestrator instead of a flat pipeline.

**Why agents?**
- **Separation of concerns**: Each agent handles one responsibility (retrieval, conversation management, answer generation).
- **Independent testability**: Each agent can be unit-tested in isolation.
- **Flexible orchestration**: The orchestrator controls flow and handles failures at each step.

---

## Design Decisions

### How hallucination is prevented
1. **Strict system prompt**: "Answer ONLY from provided context"
2. **No-context fallback**: If FAISS returns nothing, we don't call the LLM at all.
3. **Low temperature (0.1)**: Keeps answers factual, not creative.
4. **Source references**: Every answer shows which chunks were used, so users can verify.
5. **Re-ranking**: Keyword overlap check ensures retrieved chunks are actually relevant.

### Why FastAPI BackgroundTasks?
To fulfill the requirement of **Async Processing** without bloating the repository with heavy external services like Celery and Redis, we use FastAPI's built-in `BackgroundTasks`. 
- Uploads return immediately so the user/API is not blocked.
- Document extraction, chunking, and FAISS indexing occur in an isolated background thread dynamically bound to its own local DB session.

### Why this chunking strategy?
- **Paragraph-aware splitting**: Preserves semantic boundaries instead of cutting mid-sentence.
- **500-800 token chunks**: Large enough for context, small enough for precise retrieval.
- **100-150 token overlap**: Ensures no information is lost at chunk boundaries.

### Why FAISS?
- **Fast**: In-memory similarity search, sub-millisecond for thousands of vectors.
- **Persistent**: Index saves to disk and reloads on startup effortlessly alongside SQLite.

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API | FastAPI | REST API with auto-docs |
| Database | SQLite | Document & conversation storage (Lightweight) |
| Async Queue | FastAPI BackgroundTasks | Async document processing without Redis |
| Vector Store | FAISS | Similarity search |
| Embeddings | Sentence Transformers (MiniLM) | Text → vector |
| LLM | Groq (LLaMA 4 Scout) | Answer generation |
| Frontend | Vanilla HTML/CSS/JS | Premium dark-mode chat UI |
| Container | Docker Compose | One-command deployment |

---

## Quick Start (Docker)

### Prerequisites
- Docker and Docker Compose installed
- A Groq API key (get one at https://console.groq.com)

### Setup

1. **Clone the repo:**
```bash
git clone <repo-url>
cd hiring-hub-assignment
```

2. **Set your Groq API key:**
Open `.env` (or create if missing) and set:
```bash
GROQ_API_KEY=gsk_your_key_here
LLM_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
LLM_MAX_TOKENS=4000
```

3. **Start the application seamlessly:**
```bash
docker-compose up --build
```
> Note: The docker-compose utilizes SQLite and FAISS mapped to a single `./data` volume, completely bypassing the need for Redis/Postgres and launching immediately!

4. **Open the app:**
- Frontend CLI UI: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## API Usage

### Upload a Document (Async)
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@sample_docs/ai_overview.txt"
```

Response:
```json
{
  "id": 1,
  "filename": "ai_overview.txt",
  "status": "UPLOADING",
  "message": "Document uploaded successfully. Processing will begin shortly."
}
```

### Check Processing Status
```bash
curl http://localhost:8000/api/documents/1/status
```

Response:
```json
{
  "id": 1,
  "filename": "...",
  "status": "READY",
  "chunk_count": 12
}
```

### Ask a Question
```bash
curl -X POST http://localhost:8000/api/questions/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the types of AI?",
    "document_id": 1
  }'
```

Response:
```json
{
  "answer": "Based on the document, AI can be categorized into three types...",
  "conversation_id": 1,
  "document_id": 1,
  "question": "What are the types of AI?",
  "source_chunks": [...]
}
```
