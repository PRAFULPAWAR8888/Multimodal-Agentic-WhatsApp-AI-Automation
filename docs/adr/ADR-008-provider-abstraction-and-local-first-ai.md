# ADR-008: Provider Abstraction and Local-First Open-Source AI Strategy

## Status
Accepted

## Context
Deploying an AI platform that exclusively depends on proprietary commercial APIs (such as OpenAI, Anthropic, or Google Gemini) introduces severe vendor lock-in, recurring operational expenses, data privacy risks (transmitting customer WhatsApp messages to external clouds), and rate-limit vulnerabilities. Conversely, running large LLMs (like 70B parameter models) locally on standard developer hardware is computationally prohibitive.

## Decision
We enforce an **Interface-First, Local-Prioritized Provider Abstraction Architecture**:
1. All AI capabilities must implement explicit abstract base classes (`LLMProvider`, `EmbeddingProvider`, `STTProvider`, `TTSProvider`, `VisionProvider`).
2. The core platform ships with **zero-cost, local-first open-source backends**:
   - **LLM**: `OllamaProvider` (supporting local open-weight models like LLaMA 3.2, Mistral, Qwen) alongside a lightweight `OpenAILLMProvider` fallback for high-throughput cloud environments.
   - **Embeddings**: Local CPU embeddings via `SentenceTransformers` (`all-MiniLM-L6-v2`) storing 384-dimensional vectors in PostgreSQL `pgvector`.
   - **STT**: `faster-whisper` (8-bit quantized on CPU) processing WhatsApp OGG/Opus audio without external API calls.
   - **TTS**: `Piper TTS` (lightweight ONNX-based neural speech synthesizer running locally on CPU).
   - **Vision & OCR**: `PaddleOCR` (CPU-optimized text and receipt reading) and `moondream2` (lightweight 1.86B parameter VLM) or local OpenCV.
3. Swapping between local and external providers is controlled strictly through configuration environment variables (`LLM_PROVIDER=ollama|openai`, `STT_PROVIDER=faster_whisper`, etc.) without altering a single line of business logic or agent graph definition.

## Consequences
- **Pros**: Zero ongoing inference cost for local development; strict data sovereignty compliance; runnable offline without internet access.
- **Cons**: Local CPU inference on smaller models may exhibit higher latency or lower reasoning nuance compared to cloud frontier models (e.g. GPT-4o).
