# ADR-005: Speech Processing Stack

## Status
Accepted

## Context
The platform must handle WhatsApp Voice Notes (OGG files) and synthesize voice responses. The development environment is CPU-only, and we require free, open-source solutions.

## Decision
- **Speech-to-Text (STT):** `faster-whisper`.
- **Text-to-Speech (TTS):** `Piper TTS`.
- **Format:** OGG/Opus.

## Consequences
- **Pros:** 
  - `faster-whisper` uses CTranslate2, making it up to 4x faster than standard Whisper and CPU-efficient with int8 quantization.
  - `Piper TTS` runs offline with ONNX and produces high-quality speech fast on CPU.
  - OGG/Opus is the native codec for WhatsApp Voice Notes.
- **Cons:** Quality may not match closed-source commercial APIs (like ElevenLabs).

## Alternatives Considered
- **OpenAI Whisper API**: Costs money per minute.
- **Google STT**: Paid service.
- **Coqui TTS**: Discontinued and harder to run efficiently on CPU.
