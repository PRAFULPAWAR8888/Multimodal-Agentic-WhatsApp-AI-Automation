# ADR-002: Agent Framework Selection

## Status
Accepted

## Context
The platform requires complex, stateful multi-agent orchestration to route intents (Supervisor) and handle specialized tasks (RAG, Vision, Voice, CRM).

## Decision
Use **LangGraph** with explicit state graph definitions rather than raw LangChain.

## Consequences
- **Pros:** Explicit state transitions are highly testable, debuggable, and easier to visualize. State is preserved across checkpoints for long-running workflows.
- **Cons:** Steeper learning curve compared to simple sequential chains.

## Alternatives Considered
- **Raw LangChain (LCEL)**: Too rigid for complex cycles and conditional multi-agent routing. State is often hidden.
- **CrewAI**: Higher abstraction but offers less control over exact flow and state mutation.
- **AutoGen**: Too experimental and difficult to seamlessly integrate into an async API backend.
