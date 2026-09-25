# Multimodal Agentic WhatsApp AI Automation Platform
## Comprehensive Architecture & Codebase Guide

---

## 1. How to Read This Document
This document is written for a junior developer. It explains everything from zero. We will explain **what** each component is, **why** it exists, and **how** it connects to the rest of the project.

Do not try to read this entire document in one day. Start from the top and understand the core message flow first (FastAPI -> Redis -> ARQ Worker -> LangGraph), then slowly read about specific agents, RAG, and Security.

---

## 2. Project in One Simple Picture

Here is the 10,000-foot view of the project:

```text
WhatsApp (User sends message)
   ↓
FastAPI (Receives the webhook, says "Got it!" quickly)
   ↓
Redis (Holds the message in a waiting line)
   ↓
ARQ Worker (Takes the message from the line when ready)
   ↓
LangGraph (The brain/orchestrator of the AI)
   ↓
Supervisor Agent (Decides which specialist should answer)
   ↓
Specialized Agents (e.g., Sales, Support, CRM, Lead)
   ↓
Tools & External Services (PostgreSQL, Vector DB, HubSpot, Calendar)
   ↓
Response generated and sent back to WhatsApp
```

---

## 3. Project Goal
The goal of this project is to build an intelligent, multi-agent AI system that can communicate with users over WhatsApp. It doesn't just chat; it takes **actions** (like booking calendar appointments, extracting lead data, or creating CRM tickets). It is "multimodal", meaning it understands text, voice notes, images, and documents.

---

## 4. Technology Stack
- **FastAPI**: The web server that receives HTTP webhooks from WhatsApp.
- **Redis**: A super-fast in-memory database used as a "queue" (waiting line) for background jobs.
- **ARQ**: The background job worker that processes tasks from Redis.
- **PostgreSQL**: The main permanent database where users, messages, and settings are stored.
- **pgvector**: An extension for PostgreSQL that allows it to store and search "vectors" (used for AI knowledge retrieval).
- **LangGraph**: A framework for building stateful, multi-actor applications with LLMs.
- **FastMCP**: Handles integrating with external tools (like HubSpot or Google Calendar) securely.

---

## 5. Complete Repository / Folders Map

If you open the project, here is what every folder does:

```text
apps/
 ├── api/       → The HTTP API layer (FastAPI). Receives webhooks and provides admin APIs.
 ├── worker/    → The background processor (ARQ). Does the heavy lifting so the API doesn't freeze.
 └── web/       → The frontend interface (React/Vite). Where humans log in to configure the bot.

src/
 └── whatsapp_agent/
      ├── agents/        → The AI brains. Contains the Supervisor, Sales, Support, etc.
      ├── config/        → Settings and environment variable loading.
      ├── core/          → Core utilities like exceptions and governance.
      ├── database/      → SQLAlchemy models (tables), repositories, and DB connection setup.
      ├── documents/     → Document parsing (e.g. PDF text extraction).
      ├── integrations/  → Code connecting to Calendar, CRM, etc.
      ├── mcp_servers/   → Standalone servers exposing external tools securely.
      ├── observability/ → Logging and tracking.
      ├── rag/           → Retrieval-Augmented Generation (Chunking, Embedding, Searching).
      ├── security/      → Passwords, JWT, and authentication.
      ├── tools/         → The specific actions agents can take (like saving a lead).
      ├── vision/        → Image understanding (Moondream/OCR).
      ├── voice/         → Audio processing (Speech-To-Text, Text-To-Speech).
      ├── whatsapp/      → Code to actually send/receive messages from Meta.
      └── workflows/     → The LangGraph setup connecting all agents together.
```

---

## 6. Important Files Explained

Let's look at the most critical files you must understand.

### `apps/api/main.py`
- **What it does**: Starts the FastAPI web server.
- **Why it exists**: Meta (WhatsApp) needs a URL to send messages to. This file creates that URL.
- **Important logic**: Connects to the database and registers routers (like `/webhooks`).

### `apps/worker/main.py`
- **What it does**: The ARQ worker process.
- **Why it exists**: If we processed AI requests inside FastAPI, the server would timeout. The worker takes its time processing AI requests in the background.
- **Important functions**: `process_whatsapp_webhook()`, `run_agent()`. 

### `src/whatsapp_agent/workflows/main_workflow.py`
- **What it does**: Defines the LangGraph workflow.
- **Why it exists**: It routes the conversation. E.g., Start -> Check Identity -> Supervisor -> Specialized Agent -> Send Response.

### `src/whatsapp_agent/database/models/whatsapp.py`
- **What it does**: Defines the PostgreSQL tables for `WhatsAppMessage`, `WhatsAppContact`, etc.
- **Why it exists**: We need a permanent record of every message sent and received.

---

## 7. FastAPI Architecture

**What is FastAPI?** A modern, fast web framework for building APIs with Python.
**Why are we using it?** WhatsApp sends HTTP POST requests (webhooks) when a user sends a message. FastAPI is excellent at receiving these quickly.
**What does it receive?** JSON payloads from Meta containing the message text/audio.
**What does it return?** It immediately returns an HTTP 200 "OK" back to Meta. It does **not** return the AI response directly (that takes too long).
**Where is it used?** `apps/api/routers/webhooks.py`.

---

## 8. Redis + ARQ Architecture

**What is Redis?** An in-memory key-value store. It is incredibly fast.
**Why do we need Redis?** We use it as a "message queue". When FastAPI gets a message, it drops a job into Redis saying "Hey, process message 123".
**Why can't AgentState replace Redis?** AgentState tracks the *current* conversation inside LangGraph. Redis tracks the *waiting line* of jobs to be processed across the entire server.
**What is ARQ?** An async job queue for Python, backed by Redis.
**Why do we need a worker?** LLM calls take 3-10 seconds. Meta requires webhooks to respond in under 3 seconds. The worker allows the system to process heavy AI tasks asynchronously.

---

## 9. LangGraph Architecture

**What is LangGraph?** A library for building stateful, multi-actor applications with LLMs, built on top of LangChain.
**Why do we need it?** Complex AI shouldn't just be one massive prompt. LangGraph lets us break logic into "nodes" (steps) and "edges" (rules for moving between steps).
**What is a graph?** A flowchart of the conversation.
**What is a node?** A Python function that does one specific thing (e.g., `supervisor_node`).
**What is an edge?** The connection between nodes. It decides where to go next based on the node's output.
**What is AgentState?** A dictionary (defined in `src/whatsapp_agent/agents/state.py`) that gets passed from node to node. It contains the message text, conversation history, and tool outputs.

---

## 10. AI Agents Breakdown

### Supervisor Agent (`agents/supervisor/agent.py`)
- **Purpose**: Reads the user's message and decides which specialized agent should handle it.
- **Input**: The user's message.
- **Output**: A JSON string saying exactly which agent to call next (e.g., "sales", "support").

### Sales Agent (`agents/sales/agent.py`)
- **Purpose**: Answers questions about pricing, products, and pitches to the customer.
- **Tools**: Has access to the Knowledge base (RAG).

### Lead Agent (`agents/lead/agent.py`)
- **Purpose**: Extracts structured information (Name, Email, Phone) from casual conversation.
- **Tools**: Native database tool `upsert_lead_record`.

### CRM Agent (`agents/crm/agent.py`)
- **Purpose**: Creates support tickets or looks up customer records in external systems like HubSpot.
- **Tools**: Connects to the `CRM_Server` MCP tool.

### Knowledge Agent (`agents/knowledge/agent.py`)
- **Purpose**: Answers general questions based on uploaded company PDFs or websites.

### Human Escalation Agent (`agents/human_escalation/agent.py`)
- **Purpose**: Detects when a user is angry or the AI cannot help, and stops the AI from replying, flagging a human to take over.

---

## 11. Complete WhatsApp Message Flow (Example)

> User sends: "I want to book an appointment tomorrow."

1. **WhatsApp**: User sends the message on their phone.
2. **Meta Webhook**: Meta's servers POST a JSON payload to our URL.
3. **FastAPI (`webhooks.py`)**: Receives the POST, saves the raw message to PostgreSQL, and calls `redis.enqueue_job("process_whatsapp_webhook", msg_id)`. Returns 200 OK to Meta.
4. **ARQ Worker (`worker/main.py`)**: Picks up the job. It finds/creates the Contact and Conversation in the DB. Enqueues a second job: `run_agent`.
5. **ARQ Worker (`run_agent`)**: Starts the LangGraph workflow (`workflows/main_workflow.py`).
6. **Supervisor Node**: Reads "book an appointment" and routes to the Scheduling Agent.
7. **Scheduling Agent**: Realizes it needs to check the calendar. Calls the `Calendar_Server` tool.
8. **Response Node**: The Agent decides on a reply: "Sure, what time tomorrow?".
9. **WhatsApp Provider**: Sends the text back to Meta's API.
10. **WhatsApp**: User receives the message on their phone.

---

## 12. Multimodal Flows

### Voice Message Flow
WhatsApp → `download_media()` → `faster_whisper` (Speech to Text) → Text inserted into AgentState → Normal Agent processing → Agent replies with Text.
*(Note: Text-to-Speech via Piper TTS is partially implemented but requires a model file).*

### Image Flow
WhatsApp → `download_media()` → `PaddleOCR` (extracts text) + `Moondream` (describes image) → Extracted data added to AgentState → Normal Agent processing.

### Document Flow
WhatsApp → `download_media()` → `pdfplumber` extracts text → Text added to AgentState → Normal Agent processing.

---

## 13. RAG Architecture (Retrieval-Augmented Generation)

**What is it?** A way to give the AI a "search engine" for your private company documents so it doesn't hallucinate.

**How THIS project implements it:**
1. **Document**: A user uploads a PDF.
2. **Text extraction**: `ingest_knowledge_source` extracts the text.
3. **Chunking**: `RecursiveTextSplitter` cuts the text into 512-token chunks so the LLM isn't overwhelmed.
4. **Embedding**: `SentenceTransformerEmbedding` turns the text chunks into math vectors (lists of 384 numbers).
5. **Vector storage**: Saved in PostgreSQL using `pgvector`.
6. **Similarity search**: When a user asks a question, we embed their question, and `pgvector` finds the closest matching math vectors in the database.
7. **LLM**: The retrieved text is given to the Knowledge Agent to answer the question.

---

## 14. Database Architecture

**Why PostgreSQL?** It is highly reliable, relational (great for linking users to messages), and with `pgvector`, it can store AI embeddings.

**Important Tables:**
- `workspaces`: The company using the software.
- `business_profiles`: Rules for the AI (Persona, Tone).
- `whatsapp_contacts`: Customers chatting with the bot.
- `whatsapp_messages`: Every message sent or received.
- `leads`: Data extracted by the Lead Agent.
- `knowledge_sources`: Uploaded PDFs for RAG.

**Migrations (Alembic)**: Alembic tracks changes to the database structure. If we add a new column to a table, Alembic writes a script to safely update the live database without losing data.

---

## 15. Security & Tool Architecture

**Tool Architecture**: 
Agents DO NOT talk to external services directly. They request a Tool Execution.
The request hits the `ToolRunner` (`registry.py`).
The `ToolRunner` checks:
1. **Permissions**: Is this workspace allowed to use this tool?
2. **Risk**: Is this a dangerous tool?
3. **Consent**: Did the user agree to have their data sent to HubSpot?
4. **Audit**: Logs the tool execution to the database.

**Authentication**: 
The API is secured using JWT (JSON Web Tokens). When an admin logs into the frontend, they get a JWT. They must send this token in the header of every API request to prove who they are.

---

## 16. CRM and Calendar Architecture

To keep the application modular, we use **FastMCP** (Model Context Protocol).
Instead of the CRM Agent having HubSpot code inside it, we built standalone MCP servers (`src/whatsapp_agent/mcp_servers/crm_server.py`).
The Agent says "Create a ticket", and the MCP Client routes that request to the CRM Server over standard input/output.
This means we can swap HubSpot for Salesforce later without touching the AI Agents!

*Current Status: The interfaces exist, but they are currently wired to Mock Providers (`MockCRMProvider`) for demo purposes. Real HubSpot integration is planned.*

---

## 17. Configuration and Docker

### Configuration
- `.env`: Holds secrets like `OPENAI_API_KEY` and `POSTGRES_PASSWORD`. **NEVER COMMIT THIS FILE TO GITHUB.**
- `settings.py`: Loads the `.env` variables into safe Python objects.

### Docker
Docker packages the application so it runs identically on any computer.
`docker-compose.yml` starts 5 containers:
1. **postgres**: The database.
2. **redis**: The message queue.
3. **api**: The FastAPI web server.
4. **worker**: The ARQ background job processor.
5. **web**: The Vite/React frontend admin panel.

---

## 18. Current Implementation Status

| Component | Status | Explanation |
|---|---|---|
| **FastAPI Webhook** | VERIFIED COMPLETE | Fully receives messages and passes to ARQ. |
| **ARQ Worker** | VERIFIED COMPLETE | Fully implemented. Background jobs run perfectly. |
| **LangGraph / Agents** | VERIFIED COMPLETE | Supervisor, Sales, Support, Lead, CRM agents work. |
| **Document Processing** | VERIFIED COMPLETE | PDF extraction via `pdfplumber` works. |
| **RAG Ingestion** | VERIFIED COMPLETE | Chunks and embeds text into `pgvector` locally. |
| **CRM / Calendar Sync** | PARTIALLY COMPLETE| Code is fully wired and executes, but uses Mock providers. |
| **Admin API** | VERIFIED COMPLETE | Endpoints exist to update AI Personas and Business Profiles. |
| **Voice TTS** | BROKEN / STUB | The code exists, but requires manual download of Piper models. |
| **Testing** | MISSING | The `tests/` folder exists, but extensive test cases are not implemented. |

---

## 19. Beginner Learning Roadmap

How you should study this project to become an expert:

1. **FastAPI & Webhooks** (Look at `apps/api/routers/webhooks.py`)
2. **Redis & Background Jobs** (Look at `apps/worker/main.py`)
3. **Database Models** (Look at `src/whatsapp_agent/database/models/`)
4. **LangGraph Basics** (Look at `src/whatsapp_agent/workflows/main_workflow.py`)
5. **Agents** (Look at `src/whatsapp_agent/agents/supervisor/agent.py`)
6. **Tool Governance** (Look at `src/whatsapp_agent/tools/registry.py`)
7. **RAG & Vector DB** (Look at `src/whatsapp_agent/rag/`)

Take your time. Read one file per day, understand the inputs and outputs, and trace how a message flows through the system.

Good luck! 🚀
