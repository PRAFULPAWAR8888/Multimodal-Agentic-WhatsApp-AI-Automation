# Testing Strategy & Quality Assurance

This document defines the testing architecture, tiers of verification, coverage targets, and test execution standards.

---

## 1. Testing Pyramid

```
                / \
               /   \      E2E Scenarios (8 Core Workflows)
              /  ▲  \     - Webhook -> Intent -> Agent -> Tool -> Response
             /───────\
            /         \   Integration / API Tests
           /     ▲     \  - FastAPI endpoints, Auth, Webhook HMAC, DB Repositories
          /─────────────\
         /               \ Unit Tests
        /        ▲        \ - Settings, Chunking, Embeddings, Schema Parsers,
       /                   \  Provider abstractions, Risk checks, Guardrails
      /─────────────────────\
```

---

## 2. Mandatory Test Coverage Targets
- **Unit Tests**: Minimum 85% branch coverage on core domain logic (`core/`, `whatsapp/`, `rag/`, `agents/state.py`).
- **Provider Tests**: 100% test coverage with mock providers so test suite executes completely offline without external internet access or API fees.
- **Tenant Isolation**: Mandatory regression tests attempting cross-tenant data operations to verify 403 Forbidden or 404 Not Found.

---

## 3. The 8 Mandatory E2E Verification Scenarios

| Scenario | Trigger / Input | Expected Agent Path | Final Outcome |
|:---|:---|:---|:---|
| **1. Text Knowledge Query** | Customer asks: "What is your warranty policy?" | Supervisor -> Knowledge Agent -> RAG Search -> Grounded Answer | Returns accurate policy text grounded in vector chunks |
| **2. Voice Note Inquiry** | Voice audio in Hindi/English sent to WhatsApp | STT -> Language Detection -> Supervisor -> Sales Agent -> TTS | Returns voice note response in customer language |
| **3. Image Troubleshooting** | Customer sends photo of a broken product | Image Validator -> Vision/OCR -> Support Agent | Support agent identifies defect and provides troubleshooting steps |
| **4. Document Catalog Query**| Customer sends PDF specification | PDF Ingestion -> Text Splitter -> Vector Index -> Grounded QA | Agent answers specific queries based on document contents |
| **5. Purchase Intent Capture**| Customer says: "I want to buy 50 units for my company" | Supervisor -> Lead Qualification Agent -> Schema Extraction | Extracts structured lead (quantity, timeline, budget) |
| **6. Meeting Scheduling** | Customer asks: "Can we schedule a demo tomorrow?" | Supervisor -> Scheduling Agent -> Availability Check | Returns available slots and confirms booking without overlap |
| **7. Human Escalation** | Customer says: "Let me talk to a human manager" | Supervisor -> Human Escalation Agent -> AI Pause | Conversation paused, notification logged, human takeover enabled |
| **8. Unauthorized Tool Abuse**| Prompt injection attempting to delete CRM records | Supervisor -> Tool Gatekeeper -> Permission Check | Tool execution blocked, security alert emitted to audit log |

---

## 4. Test Commands
```bash
# Run complete test suite
pytest

# Run unit tests only
pytest tests/unit

# Run API tests with test coverage
pytest --cov=whatsapp_agent tests/
```
