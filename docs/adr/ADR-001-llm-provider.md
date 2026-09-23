# ADR-001: Use OpenAI API as Primary LLM Provider with Provider Abstraction

## Status
Accepted

## Context
We need a robust, reasoning-capable LLM to drive LangGraph agents, multi-step planning, and RAG processing. However, the development environment is a CPU-only machine, rendering local high-parameter models (like LLaMA 3 70B) unusable. At the same time, we do not want strict vendor lock-in.

## Decision
We will use the **OpenAI API (gpt-4o-mini)** as the default LLM. However, all LLM interactions MUST go through an `LLMProvider` abstract interface.

## Consequences
- **Pros:** We get fast, reliable intelligence without local hardware constraints. The provider abstraction ensures we can easily swap to Ollama, Anthropic, or HuggingFace later.
- **Cons:** Incurs per-token costs for API usage. Requires internet access.

## Alternatives Considered
- **Ollama locally**: Models capable of complex agentic reasoning are too slow on CPU.
- **HuggingFace API**: Less capable for complex tool use and JSON parsing.
