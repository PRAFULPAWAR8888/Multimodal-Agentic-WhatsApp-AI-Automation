# API Specification (v1)

All endpoints are versioned under `/api/v1` except system-level health probes.

---

## 1. System & Health Probes

### `GET /healthz`
Returns overall service liveness.

### `GET /ready`
Returns service readiness (verifies active connection to PostgreSQL and Redis).

---

## 2. Authentication & Workspaces

### `POST /api/v1/auth/register`
Register a new tenant user and create default workspace.
- **Request Body**:
  ```json
  {
    "email": "owner@company.com",
    "password": "SecurePassword123!",
    "full_name": "Jane Doe",
    "business_name": "Acme Electronics"
  }
  ```
- **Response**: `201 Created` with user details, workspace metadata, and JWT tokens (`access_token`, `refresh_token`).

### `POST /api/v1/auth/login`
Authenticate with email and password to receive JWT credentials.

### `POST /api/v1/auth/refresh`
Rotate refresh token to obtain a fresh access token.

---

## 3. WhatsApp Integration

### `GET /api/v1/webhooks/whatsapp`
Handles Meta WhatsApp Cloud API verification challenge (`hub.mode`, `hub.challenge`, `hub.verify_token`).

### `POST /api/v1/webhooks/whatsapp`
Receives incoming WhatsApp webhook events (text, voice, image, document, delivery receipts).
- **Security**: Validates HMAC-SHA256 signature in `X-Hub-Signature-256` header.
- **SLA**: Immediately returns `200 OK` and enqueues event into Redis ARQ worker.

---

## 4. Conversations & Messages

### `GET /api/v1/conversations`
List conversations for active workspace with pagination and status filters (`active`, `human_escalated`, `closed`).

### `GET /api/v1/conversations/{id}`
Retrieve full message history and metadata for a conversation.

### `POST /api/v1/conversations/{id}/takeover`
Human agent takes over conversation: pauses AI processing, sets conversation status to `human_takeover`.

### `POST /api/v1/conversations/{id}/resume`
Resumes autonomous AI processing for the conversation.

---

## 5. Knowledge Base & RAG

### `POST /api/v1/knowledge/upload`
Uploads document (PDF, TXT, DOCX) for automated text extraction, chunking, embedding, and vector storage.

### `GET /api/v1/knowledge/sources`
List all ingested knowledge sources for the active workspace.

---

## 6. AI Playground & Simulation

### `POST /api/v1/playground/chat`
Simulate WhatsApp interaction in web UI: runs LangGraph pipeline and returns response along with safe execution metadata (selected agent, intent, latency, confidence, executed tools) without leaking private chain-of-thought.
