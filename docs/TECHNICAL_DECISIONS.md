# Technical Decisions Record (TDR)

This document records the foundational technical and architectural decisions for the **Multimodal Agentic WhatsApp AI Automation Platform**. It complements the individual Architecture Decision Records (ADRs) found in `docs/adr/`.

---

## 1. Modular Monolith vs. Microservices Architecture

- **Decision**: Build the platform as a **Modular Monolith** containing clean boundaries (`apps/api`, `apps/worker`, `apps/web`, and domain modules under `src/whatsapp_agent/`).
- **Rationale**: 
  - Prevents premature distributed systems complexity (distributed tracing, network partitions, multi-repo synchronization).
  - Maximizes developer velocity during initial phases while maintaining strict boundary separation (Presentation, Application, Domain, Infrastructure).
  - Permits future extraction of high-compute subsystems (e.g. Media/Speech workers, MCP tool runners) into separate microservices if load mandates.
- **Reference**: Clean Architecture, SOLID Principles, 12-Factor App.

---

## 2. Mandatory Provider Abstraction Layer

- **Decision**: Zero hardcoded coupling to proprietary AI or external SaaS vendors. Every external capability must be hidden behind an abstract interface:
  - `LLMProvider` (Ollama, HuggingFace, OpenAI, vLLM)
  - `EmbeddingProvider` (SentenceTransformers, pgvector, Ollama)
  - `STTProvider` (faster-whisper, whisper.cpp, OpenAI Whisper)
  - `TTSProvider` (Piper TTS, gTTS, OpenAI TTS)
  - `VisionProvider` (moondream2, OpenCV, PaddleOCR, LLaVA)
  - `WhatsAppProvider` (Official Cloud API, MockWhatsAppProvider)
  - `CRMProvider` (HubSpot, MockCRMProvider)
  - `CalendarProvider` (Google Calendar, Outlook, MockCalendarProvider)
  - `StorageProvider` (Local, S3, GCS)
- **Rationale**:
  - Prioritizes **Free / Open-Source / Local-First** execution for development and self-hosted deployments.
  - Development and automated testing runs 100% locally without external API keys or recurring charges.
  - Production deployments can switch to commercial APIs or local high-throughput servers (e.g., vLLM) via environment variables without altering application business logic.

---

## 3. Asynchronous Worker & Queue: ARQ (Async Redis Queue)

- **Decision**: Select **ARQ** over Celery and RQ for asynchronous task execution.
- **Rationale**:
  - WhatsApp Cloud API mandates a synchronous HTTP 200 acknowledgment within **3.0 seconds**, or Meta initiates aggressive webhook retries.
  - Ingestion, STT transcription, LLM reasoning, RAG vector searches, and tool calls are latency-heavy (often 2–15 seconds).
  - ARQ is natively `asyncio`-first, integrating with FastAPI's async execution loop and async SQLAlchemy/Redis connections without thread pool exhaustion or gevent/eventlet monkey-patching.
  - Celery is historically synchronous and introduces significant boilerplate and memory overhead.

---

## 4. Multi-Agent Orchestration: LangGraph

- **Decision**: Adopt **LangGraph** (StateGraph) for supervisor routing and specialized agent workflows.
- **Rationale**:
  - Agentic interactions are stateful, cyclic, and branch dynamically based on intent, confidence, tool results, and escalation requirements.
  - LangGraph provides explicit, inspectable state graphs where each node is a discrete function taking `AgentState` and returning state deltas.
  - Eliminates hidden prompt chaining and magic abstractions common in monolithic agent frameworks.
  - Clean separation between Supervisor (Intent & Routing), Specialists (Knowledge, Sales, Support, Lead, Scheduling, Media, Voice, CRM), and Guardrails (Human Escalation, Tool Permission Enforcers).

---

## 5. Tool Protocol & Safety Boundary: Model Context Protocol (MCP) + Strict RBAC

- **Decision**: Standardize tool schemas and execution via **Model Context Protocol (MCP)** using `fastmcp`, while enforcing safety, authorization, and risk classification **outside** MCP.
- **Rationale**:
  - Standardizes tool contracts across agents and external tool servers.
  - **Crucial Security Rule**: MCP is an integration mechanism, NOT a security boundary.
  - All tool calls must pass:
    1. Schema Validation (Pydantic)
    2. Agent Permission Check (Can this agent call this tool?)
    3. User/Workspace RBAC Check (Does the tenant have this tool enabled?)
    4. Risk Level Gatekeeper (LOW: auto-execute; MEDIUM: validate; HIGH: require human confirmation/approval)
    5. Immutable Audit Logging.

---

## 6. Multi-Tenancy & Workspace Data Isolation

- **Decision**: Shared-database, shared-schema multi-tenancy enforced at the application query and repository layer via mandatory `workspace_id` filtering.
- **Rationale**:
  - Balances operational simplicity with database resource efficiency.
  - Every tenant entity (`WhatsAppAccount`, `WhatsAppConversation`, `WhatsAppMessage`, `KnowledgeSource`, `DocumentChunk`, `Lead`, `AuditLog`, etc.) includes a non-nullable foreign key to `workspaces.id`.
  - Repositories and queries systematically enforce workspace filtering; cross-tenant data access is caught by unit and integration tests.

---

## 7. Multimodal Ingestion Pipeline

- **Decision**: Segregate message ingestion from multimodal processing.
  - Voice notes (OGG/Opus): Validated, preprocessed, transcribed via `faster-whisper` (int8 CPU quantization).
  - Images (JPEG/PNG/WebP): Validated for magic bytes, dimensions, and malware heuristics; OCR performed via `PaddleOCR` and visual QA via `moondream2` or local VLM.
  - Documents (PDF/DOCX/TXT): Validated, text extracted via `PyMuPDF`/`pdfplumber`, chunked via recursive character splitter, embedded via `sentence-transformers` (`all-MiniLM-L6-v2`), stored in PostgreSQL `pgvector`.
- **Rationale**:
  - Eliminates blocking calls on webhooks.
  - Fully runnable on standard CPU infrastructure for developer onboarding.
