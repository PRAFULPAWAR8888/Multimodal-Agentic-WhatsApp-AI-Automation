# Master Project Plan & Execution Roadmap

This document outlines the progressive, phased implementation roadmap for the **Multimodal Agentic WhatsApp AI Automation Platform**.

---

## Roadmap Overview

```
Phase 1: Foundation (Architecture, Git, Docker, Tooling)
   ↓
Phase 2: Backend Core (FastAPI, Dependency Injection, Auth Foundation)
   ↓
Phase 3: Database Engine (PostgreSQL, pgvector, SQLAlchemy 2.x, Alembic)
   ↓
Phase 4: Frontend Foundation (React 18, Vite, TypeScript, Tailwind)
   ↓
Phase 5: Multi-Tenancy (Workspaces, Members, RBAC, Business Profiles)
   ↓
Phase 6: WhatsApp Layer (Provider Abstraction, Cloud API, Webhooks, Mock)
   ↓
Phase 7: Provider-Independent AI (LLM Abstraction, Ollama, Open Weights)
   ↓
Phase 8: Supervisor Agent (LangGraph StateGraph, Intent Routing)
   ↓
Phase 9: RAG Engine (Ingestion, Chunking, Embeddings, pgvector Search)
   ↓
Phase 10: Specialized Agents (Knowledge, Sales, Support, Lead Qualification)
   ↓
Phase 11: Voice Messages (Audio Validation, faster-whisper STT, Piper TTS)
   ↓
Phase 12: Vision & Documents (PaddleOCR, moondream2, PyMuPDF)
   ↓
Phase 13: Lead Automation (Structured Extraction, Lead Scoring)
   ↓
Phase 14: CRM Integration (HubSpot Provider, Least-Privilege OAuth, Mock)
   ↓
Phase 15: Calendar Automation (Slot Availability, Booking Confirmation)
   ↓
Phase 16: Human Collaboration (Live Inbox, AI Pause, Takeover, Resume)
   ↓
Phase 17: Voice Call Architecture (Platform Dependent Abstraction & Simulator)
   ↓
Phase 18: Security & Governance (Prompt Injection Defense, Tool Permissions, Auditing)
   ↓
Phase 19: Comprehensive Testing (Unit, Integration, E2E Scenarios, Isolation)
   ↓
Phase 20: Observability (Structured Logs, Prometheus Metrics, OpenTelemetry)
   ↓
Phase 21: Deployment & Production Readiness (Docker Compose, Health Checks)
```

---

## Detailed Phase Breakdown

| Phase | Phase Name | Description | Deliverables | Status |
|:---:|:---|:---|:---|:---:|
| **1** | **Foundation** | Repository setup, documentation, Git, linting, Docker Compose | `docs/`, `docker-compose.yml`, `pyproject.toml` | 🔄 IN PROGRESS |
| **2** | **Backend Core** | FastAPI application factory, middleware, structured errors | `apps/api/main.py`, exception handlers | 🔄 IN PROGRESS |
| **3** | **Database Engine** | PostgreSQL with pgvector, Alembic migrations, tenant models | `src/whatsapp_agent/database/`, `migrations/` | 🔄 IN PROGRESS |
| **4** | **Frontend Foundation** | React, Vite, Tailwind, Zustand dashboard shell | `apps/web/` | 🔄 IN PROGRESS |
| **5** | **Multi-Tenancy** | Workspaces, WorkspaceMembers, RBAC, Business Profile persona | Repositories, auth dependencies | 📋 PLANNED |
| **6** | **WhatsApp Integration** | Webhook verification, HMAC validation, Mock + Official Provider | `whatsapp/providers/`, `webhook_parser.py` | 🔄 IN PROGRESS |
| **7** | **Local / Independent AI** | Base `LLMProvider`, `OllamaProvider`, `OpenAIProvider`, retry | `agents/llm_provider.py` | 🔄 IN PROGRESS |
| **8** | **Supervisor Agent** | LangGraph intent routing, confidence gating, context assembly | `agents/supervisor/`, `agents/state.py` | 🔄 IN PROGRESS |
| **9** | **RAG Engine** | Chunking, sentence-transformers, pgvector cosine search | `rag/chunking/`, `rag/retrieval/` | 🔄 IN PROGRESS |
| **10** | **Specialized Agents** | Knowledge, Sales, Support, Lead agents implemented | `agents/{knowledge,sales,support,lead}` | 📋 PLANNED |
| **11** | **Voice Processing** | faster-whisper STT, Piper TTS, language detection (EN/HI/MR) | `voice/stt/`, `voice/tts/` | 📋 PLANNED |
| **12** | **Vision & Documents** | PaddleOCR, moondream2 vision understanding, PDF parsing | `vision/`, `documents/` | 📋 PLANNED |
| **13** | **Lead Automation** | Lead schema extraction, score computation, CRM preparation | `agents/lead/` | 📋 PLANNED |
| **14** | **CRM Integration** | HubSpot provider, OAuth token management, mock provider | `crm/providers/` | 📋 PLANNED |
| **15** | **Calendar Automation** | Google/Outlook provider, double-booking prevention, mock | `calendar/providers/` | 📋 PLANNED |
| **16** | **Human Takeover** | Live inbox WebSocket, AI pause/resume, handover reason | `apps/web/src/pages/inbox/`, state controls | 📋 PLANNED |
| **17** | **Voice Calling** | Real-time audio provider abstraction, call simulator | `voice/telephony/` | ⚠️ PLATFORM DEPENDENT |
| **18** | **Security & Governance** | Tool permission checking, prompt injection defenses, audit | `security/`, `audit.py` | 📋 PLANNED |
| **19** | **Testing Suite** | Unit, API, Agent, RAG, E2E 8 scenario validation | `tests/` | 🔄 IN PROGRESS |
| **20** | **Observability** | Prometheus exporter, OpenTelemetry traces, structlog | `observability/` | 📋 PLANNED |
| **21** | **Deployment** | Production Dockerfiles, production compose, runbook | `Dockerfile.*`, `scripts/` | 📋 PLANNED |

---

## MVP Vertical Slice Target (Immediate Milestone)

The first complete vertical slice to deliver and verify comprises:
1. **Authentication & Multi-Tenant Workspace Setup** (Owner/Admin registration and workspace binding).
2. **Provider-Independent AI Core** (Abstract `LLMProvider` with local Ollama support and mock fallback).
3. **WhatsApp Webhook Layer** (HMAC-SHA256 signature verification and Mock WhatsApp Provider).
4. **LangGraph Supervisor + Knowledge Agent with RAG** (Ingest text/FAQ -> pgvector cosine search -> grounded answer generation).
5. **Basic Lead Qualification** (Extract structured contact and purchase intent data).
6. **Frontend Dashboard Shell & Playground** (Inspect conversations, test LLM reasoning, review safe metadata without private CoT leakage).
