# Architectural Overview & Component Topology

## 1. System Topology

```
                              +---------------------------------------------+
                              |              Customer Clients               |
                              |   (WhatsApp Mobile / Desktop / Web Client)  |
                              +---------------------------------------------+
                                                     |
                                                     | HTTPS / Webhook
                                                     v
+-------------------------------------------------------------------------------------------------------------+
|                                        FastAPI Application Server                                           |
|                                                                                                             |
|  +---------------------------+  +--------------------------------+  +------------------------------------+  |
|  |     Health & Probes       |  |       Auth & Workspace         |  |      WhatsApp Ingestion Router     |  |
|  | (/healthz, /ready, /live) |  |   (/auth/register, /login)     |  |    (/webhooks/whatsapp)            |  |
|  +---------------------------+  +--------------------------------+  +------------------------------------+  |
|                                                                                        |                    |
|                                  Fast acknowledgment (<3s)                             | Enqueue Job        |
+----------------------------------------------------------------------------------------┼--------------------+
                                                                                         |
                                                                                         v
                                                                             +-----------------------+
                                                                             |   Redis Broker / ARQ  |
                                                                             +-----------------------+
                                                                                         |
                                                                                         v
+-------------------------------------------------------------------------------------------------------------+
|                                            ARQ Background Workers                                           |
|                                                                                                             |
|  +---------------------------+  +--------------------------------+  +------------------------------------+  |
|  |     Media Downloader      |  |         Audio Pipeline         |  |         Vision & OCR Engine        |  |
|  |   (Sandboxed storage)     |  | (faster-whisper, Piper TTS)    |  |     (PaddleOCR, moondream2)        |  |
|  +---------------------------+  +--------------------------------+  +------------------------------------+  |
|                |                                                                                            |
|                v                                                                                            |
|  +-------------------------------------------------------------------------------------------------------+  |
|  |                                  LangGraph Multi-Agent Orchestrator                                   |  |
|  |                                                                                                       |  |
|  |                 +------------------------------------------------------------------+                  |  |
|  |                 |                         Supervisor Agent                         |                  |  |
|  |                 |             (Intent Detection & Modality Gating)                 |                  |  |
|  |                 +------------------------------------------------------------------+                  |  |
|  |                                                  |                                                    |  |
|  |         +-------------------+--------------------+-------------------+--------------------+           |  |
|  |         |                   |                    |                   |                    |           |  |
|  |         v                   v                    v                   v                    v           |  |
|  |  +--------------+   +---------------+    +---------------+   +---------------+   +-----------------+  |  |
|  |  |  Knowledge   |   |  Sales Agent  |    | Support Agent |   |  Lead Agent   |   | Scheduling Ag.  |  |  |
|  |  +--------------+   +---------------+    +---------------+   +---------------+   +-----------------+  |  |
|  +-------------------------------------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------------------------+
                                      |                                   |
                                      v                                   v
             +------------------------------------+              +----------------------------------+
             |        PostgreSQL Database         |              |        External Platforms        |
             |  - Relational Models & Workspaces  |              |  - WhatsApp Cloud Outbound API   |
             |  - pgvector Document Chunks (384d) |              |  - HubSpot CRM API               |
             |  - Immutable Audit Logs            |              |  - Google / Outlook Calendar API |
             +------------------------------------+              +----------------------------------+
```

## 2. Component Boundaries
- **FastAPI**: Strictly ingress, authentication, request validation, and lightweight read operations.
- **ARQ Worker**: Executes all asynchronous, I/O-intensive, and compute-heavy pipelines (media processing, LLM generation, tool invocations).
- **LangGraph**: Manages workflow state transitions, conversation checkpoints, and dynamic agent delegation.
- **PostgreSQL**: Acts as both the single source of truth for transactional multi-tenant data and vector store for knowledge retrieval.
