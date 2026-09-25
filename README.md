<<<<<<< HEAD
# Multimodal-Agentic-WhatsApp-AI-Automation
=======
# Multimodal Agentic WhatsApp AI Automation Platform

## Project Overview
A production-ready platform that leverages multi-agent orchestration, robust RAG pipelines, and free/open-source multimodal models (STT, TTS, Vision, OCR) to automate WhatsApp interactions.

## Architecture

```
+----------------+      +-------------------+      +------------------+
| WhatsApp Cloud | <--> | Webhook Server    | ---> | ARQ Async Worker |
| API            |      | (FastAPI, Redis)  |      | (Python)         |
+----------------+      +-------------------+      +------------------+
                                                            |
+-----------------------------------------------------------+
|
v
+------------------+     +-------------------+     +------------------+
| LangGraph        |     | Multimodal Stack  |     | PostgreSQL +     |
| Supervisor Agent | <-> | (Whisper, Piper,  | <-> | pgvector         |
| + Specialists    |     | moondream2, OCR)  |     | (Data & Memory)  |
+------------------+     +-------------------+     +------------------+
        |
        v
+------------------+
| fastmcp Tool     |
| Server           |
+------------------+
```

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2 |
| Orchestration | LangGraph, ARQ (Redis Queue) |
| Database | PostgreSQL, pgvector, Redis, Alembic |
| LLM | OpenAI API (gpt-4o-mini) via Provider Abstraction |
| STT / TTS | faster-whisper (CPU), Piper TTS (Offline) |
| Vision & OCR | moondream2 (Transformers), PaddleOCR |
| Tools/MCP | fastmcp library |
| Voice Calls | aiortc (WebRTC) |
| Frontend | React 18, TypeScript, Vite, Tailwind, Zustand |
| Deployment | Docker, Docker Compose |

## Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Node.js 20+
- OpenAI API Key

## Quickstart

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd "Multimodal Agentic WhatsApp AI Automation Platform"
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY to .env
   ```

3. **Start Docker services:**
   ```bash
   docker-compose up -d db redis
   ```

4. **Run Migrations (Backend):**
   ```bash
   cd backend
   pip install -r requirements.txt
   alembic upgrade head
   ```

5. **Start Application:**
   ```bash
   # Terminal 1: Backend
   uvicorn app.main:app --reload
   
   # Terminal 2: Worker
   arq app.worker.WorkerSettings

   # Terminal 3: Frontend
   cd frontend
   npm install
   npm run dev
   ```

## Exact Commands

**Windows PowerShell:**
```powershell
cp .env.example .env
docker-compose up -d db redis
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
# New tab:
.\venv\Scripts\activate
arq app.worker.WorkerSettings
```

**Linux/Mac:**
```bash
cp .env.example .env
docker compose up -d db redis
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
# New tab:
source venv/bin/activate
arq app.worker.WorkerSettings
```

## Project Structure
```
.
├── backend/          # FastAPI application, agents, tools, db models
├── frontend/         # React frontend application
├── docs/             # Architecture, project plan, ADRs, security
├── docker-compose.yml
└── README.md
```

## Development Workflow
1. Write tests for new features.
2. Implement backend features.
3. Validate API changes.
4. Implement frontend consumption.

## Testing Commands
```bash
pytest
pytest --cov=app tests/
```

## Status

| Feature | Status |
|---------|--------|
| Provider Abstractions | PLANNED |
| Agent Orchestration | PLANNED |
| WhatsApp Mock API | MOCK |
| Multimodal Processing | PLANNED |
| MCP Tool Server | PLANNED |
| Real WhatsApp Integration| PLATFORM DEPENDENT |

## License
MIT License
>>>>>>> 174a187 (first commit)
