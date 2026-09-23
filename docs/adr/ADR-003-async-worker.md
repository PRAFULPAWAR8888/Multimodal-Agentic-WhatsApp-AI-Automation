# ADR-003: Async Worker Engine

## Status
Accepted

## Context
WhatsApp webhooks require strict latency (often <3 seconds SLA to acknowledge). The processing of these messages (LLM inference, DB queries, tool usage) is slow. We need an asynchronous task queue.

## Decision
Use **ARQ** (Async Redis Queue).

## Consequences
- **Pros:** Native async/await support in Python. Extremely lightweight compared to alternatives. Uses Redis, which is already in our stack.
- **Cons:** Less ecosystem tooling (like monitoring dashboards) compared to Celery.

## Alternatives Considered
- **Celery**: Sync-first design, very heavy, steep learning curve.
- **RQ**: Synchronous by default.
- **Dramatiq**: Good, but ARQ's tight async/await integration makes it superior for FastAPI.
