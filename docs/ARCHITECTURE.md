# System Architecture Specification

## 1. System Vision & Objective

The **Multimodal Agentic WhatsApp AI Automation Platform** acts as an enterprise-grade AI communication and automation layer bridging customer interactions on WhatsApp with business operations, CRM systems, calendars, databases, and operational workflows.

```
Customers (Text, Voice, Images, Documents)
                  │
                  ▼
        WhatsApp Cloud API / Webhook
                  │
                  ▼
         FastAPI Ingestion Layer
       (Signature verify, Auth, Ack < 3s)
                  │
                  ▼
         Redis Queue (ARQ Workers)
                  │
                  ▼
       Modality Preprocessing & STT / OCR
                  │
                  ▼
        LangGraph Supervisor Agent
                  │
      ┌───────────┼───────────┬───────────┐
      ▼           ▼           ▼           ▼
  Knowledge     Sales      Support      Lead
    Agent       Agent       Agent       Agent
      │           │           │           │
      ▼           ▼           ▼           ▼
  Media Agent  Voice Agent Scheduling    CRM
                           Agent        Agent
      │           │           │           │
      └───────────┴─────┬─────┴───────────┘
                        ▼
            Tool Layer & Guardrails
      (Schema, RBAC, Risk Check, Audit)
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
     PostgreSQL      HubSpot        Google /
    + pgvector         CRM          Outlook
         │              │           Calendar
         └──────────────┼──────────────┘
                        ▼
               Human Escalation Gate
                        │
                        ▼
                 Response Engine
             (Text, TTS Voice, Media)
                        │
                        ▼
               WhatsApp Outbound API
```

---

## 2. Clean Architecture & Layering

The codebase is organized following **Clean Architecture** and the **SOLID** principles, maintaining strict separation between concerns:

```
┌────────────────────────────────────────────────────────┐
│ Presentation Layer                                     │
│  - FastAPI Endpoints (apps/api/routers)                │
│  - Webhook Controllers & Request Parsers               │
│  - WebSocket / SSE Handlers                            │
│  - React Dashboard (apps/web)                          │
├────────────────────────────────────────────────────────┤
│ Application Layer                                      │
│  - Agent Workflows & State Graph (LangGraph)           │
│  - Use Cases & Application Services (services/)        │
│  - Background Tasks (apps/worker)                      │
│  - Tool Orchestration & Guardrails                     │
├────────────────────────────────────────────────────────┤
│ Domain Layer                                           │
│  - Domain Entities & Value Objects                     │
│  - Agent Specifications & State Definitions            │
│  - Business Rules, Lead Qualification Criteria         │
│  - Risk Classifications (LOW, MEDIUM, HIGH)            │
├────────────────────────────────────────────────────────┤
│ Infrastructure Layer                                   │
│  - Database Engine & Repositories (SQLAlchemy 2.x)     │
│  - pgvector Vector Storage & Indexing                  │
│  - Redis Caching & Queue Management                    │
│  - Provider Implementations (Ollama, Whisper, Piper)   │
│  - External Integrations (WhatsApp, HubSpot, Calendar) │
│  - Observability & Structured Logging                  │
└────────────────────────────────────────────────────────┘
```

**Rule**: Business logic must NEVER reside inside API route handlers. Route handlers deserialize inputs, enforce authentication, call application services or workflows, and return standardized response schemas.

---

## 3. Provider Abstraction Architecture

To guarantee vendor independence, no business logic directly instantiates third-party or proprietary SDKs. Every external capability is abstracted behind an explicit interface.

```
                      +-------------------+
                      |   «interface»     |
                      |   LLMProvider     |
                      +-------------------+
                      | + complete()      |
                      | + complete_json() |
                      +-------------------+
                                ^
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
+-------------------+  +-------------------+  +-------------------+
|  OllamaProvider   |  | HuggingFaceProv.  |  |  OpenAIProvider   |
| (Local / Free)    |  | (Open Weights)    |  | (External Backup) |
+-------------------+  +-------------------+  +-------------------+
```

Similar abstraction hierarchies exist for:
- `EmbeddingProvider` -> `SentenceTransformersEmbedding` | `OllamaEmbedding` | `OpenAIEmbedding`
- `STTProvider` -> `FasterWhisperSTT` | `WhisperCppSTT` | `OpenAIWhisperSTT`
- `TTSProvider` -> `PiperTTS` | `GTTSProvider` | `OpenAITTS`
- `VisionProvider` -> `MoondreamVision` | `PaddleOCRVision` | `OpenAIVision`
- `WhatsAppProvider` -> `OfficialWhatsAppProvider` | `MockWhatsAppProvider`
- `CRMProvider` -> `HubSpotCRMProvider` | `MockCRMProvider`
- `CalendarProvider` -> `GoogleCalendarProvider` | `OutlookCalendarProvider` | `MockCalendarProvider`

---

## 4. Multi-Agent Orchestration (LangGraph)

The supervisor acts as the central router and guardian of context.

### Supervisor Responsibilities:
1. **Context Hydration**: Injects business persona, operating hours, tone, negative constraints, and recent conversation history.
2. **Intent & Modality Detection**: Analyzes text, voice transcripts, or media metadata to determine customer intent.
3. **Routing**: Hands off execution to the specialized agent best suited for the task.
4. **Safety & Guardrails**: Evaluates confidence thresholds, flags prompt injection attempts, and triggers human escalation when criteria are met.

### Specialized Agents:
1. **Knowledge Agent**: Answers business queries grounded strictly on RAG retrieved chunks.
2. **Sales Agent**: Engages product inquiries, pricing, recommendations, and purchase intent.
3. **Support Agent**: Handles troubleshooting, FAQs, issue intake, and support tickets.
4. **Lead Qualification Agent**: Extracts structured lead attributes (budget, timeline, quantity, requirements) and computes lead scores.
5. **Media Understanding Agent**: Executes OCR and visual analysis on customer-sent screenshots, receipts, invoices, or product photos.
6. **Voice Agent**: Processes speech nuances, handles multi-language conversations (English, Hindi, Marathi, Hinglish), and determines voice response mode.
7. **Scheduling Agent**: Inspects calendar slot availability, presents options, and confirms bookings without double-booking.
8. **CRM Agent**: Performs controlled CRM lookups, contact updates, and deal creation with schema validation.
9. **Human Escalation Agent**: Pauses AI processing, captures escalation reason, notifies human staff, and transitions conversation state.

---

## 5. Tool Execution Architecture & Risk Gatekeeper

The LLM is **never** permitted to execute arbitrary commands or tools directly.

```
Agent Intent
    │
    ▼
Tool Execution Request
    │
    ▼
Tool Registry (fastmcp / schema validation)
    │
    ▼
RBAC & Permission Check (Does workspace + agent permit this tool?)
    │
    ▼
Risk Assessment
 ├── LOW Risk (e.g. search_knowledge, check_availability) -> Execute immediately
 ├── MEDIUM Risk (e.g. create_lead, update_contact) -> Validate parameters, execute
 └── HIGH Risk (e.g. schedule_appointment, create_deal, refund) -> Require validation / Human Approval
    │
    ▼
Execution Handler (Sandboxed infrastructure adapter)
    │
    ▼
Immutable Audit Log (AuditEvent logged to database)
```

---

## 6. Multimodal Pipelines

### 6.1 Audio / Voice Message Pipeline
```
Incoming WhatsApp Voice (OGG/Opus)
    ↓
Media Retrieval (Stream download to sandboxed storage)
    ↓
Audio Validation (Magic bytes check, duration limit < 120s, size limit < 16MB)
    ↓
Preprocessing (ffmpeg normalization to 16kHz mono WAV)
    ↓
STT Transcription (faster-whisper int8 CPU or Whisper.cpp)
    ↓
Language Detection (langdetect + Whisper language prob: en/hi/mr/hinglish)
    ↓
Supervisor Agent & Specialized Reasoning
    ↓
Response Mode Decision (TEXT | VOICE | TEXT+VOICE)
    ↓
If Voice: Piper TTS generation -> OGG/Opus encoding -> WhatsApp Send Media
```

### 6.2 Vision & Document Pipeline
```
Incoming Image / PDF / Document
    ↓
Media Retrieval & Sandboxed File Validation (MIME sniff, size, malware heuristics)
    ↓
Routing:
 ├── Image -> PaddleOCR (Text extraction) + moondream2 (Visual scene understanding)
 └── PDF/Doc -> PyMuPDF / pdfplumber extraction -> Recursive Chunking -> Embeddings -> pgvector
    ↓
Supervisor Agent receives structured extraction
    ↓
Specialized Agent incorporates grounded context into response
```

---

## 7. Multi-Tenancy & Data Isolation

Multi-tenancy is structured around **Workspaces**:
- A **User** can belong to multiple workspaces with distinct roles (`owner`, `admin`, `member`, `viewer`).
- Every data entity (`WhatsAppAccount`, `WhatsAppConversation`, `WhatsAppMessage`, `KnowledgeSource`, `DocumentChunk`, `Lead`, `AuditLog`, `AgentRun`) is strictly tagged with `workspace_id`.
- The database abstraction layer enforces `workspace_id` filtering on all queries, updates, and deletes.
- Cross-tenant data leaks are actively prevented and tested via automated tenant isolation suites.

---

## 8. Observability & Auditing

- **Structured Logging**: `structlog` formatting all logs as machine-parseable JSON containing `request_id`, `workspace_id`, `conversation_id`, and `agent_id`.
- **Metrics**: Prometheus instrumentation tracking webhook latency, worker queue depth, LLM inference latency, token usage, STT/TTS processing times, and tool execution success rates.
- **Audit Trails**: Every security-sensitive or high-risk operation writes an immutable record to the `audit_logs` table.
