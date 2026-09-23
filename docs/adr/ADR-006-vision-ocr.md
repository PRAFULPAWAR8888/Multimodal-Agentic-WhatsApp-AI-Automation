# ADR-006: Vision and OCR Stack

## Status
Accepted

## Context
Users will send images via WhatsApp. We need to extract text (e.g., invoices) and understand visual context. Must be free, open-source, and CPU-runnable.

## Decision
- **Vision LLM:** `moondream2` (`vikhyatk/moondream2`).
- **OCR:** `PaddleOCR`.

## Consequences
- **Pros:** 
  - `moondream2` is a 1.8B parameter model that easily runs on CPU (~3GB RAM) and provides excellent visual QA.
  - `PaddleOCR` offers superior multilingual support (crucial for mixed English/Hindi/Marathi docs) compared to standard Tesseract.
- **Cons:** Inference time on CPU for moondream2 will be slower than an API call.

## Alternatives Considered
- **GPT-4o Vision API**: Costs money per image.
- **LLaVA via Ollama**: Usually requires 7B+ parameters, which is too slow/heavy for CPU inference without a GPU.
- **Tesseract OCR**: Good, but struggles with multilingual documents out-of-the-box compared to PaddleOCR.
