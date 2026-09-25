"""
Sentence-Transformers Embedding Provider.

Generates dense vector embeddings using the sentence-transformers library.
Runs entirely on CPU — no GPU required.

Default model: all-MiniLM-L6-v2
- 384 dimensions
- ~80MB model size
- Fast CPU inference (~100ms per batch)
- Good multilingual support (English, Hindi, etc.)
- Free and open-source (Apache 2.0)

Used for:
- Document chunk embedding (during ingestion)
- Query embedding (during RAG retrieval)
- Semantic similarity search against pgvector
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import EmbeddingError
from whatsapp_agent.observability.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)

# Embedding dimension for all-MiniLM-L6-v2
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _load_model() -> "SentenceTransformer":
    """
    Load and cache the sentence-transformers model.

    Uses @lru_cache to ensure the model is only loaded once per process.
    Loading takes ~2-3 seconds on CPU — happens at first request only.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingError(
            "sentence-transformers is not installed. Run: pip install sentence-transformers"
        ) from exc

    settings = get_settings()
    model_name = settings.embedding_model

    logger.info(
        "loading_embedding_model",
        model=model_name,
        device="cpu",
    )
    start = time.monotonic()

    model = SentenceTransformer(model_name, device="cpu")

    load_time = round((time.monotonic() - start) * 1000)
    logger.info(
        "embedding_model_loaded",
        model=model_name,
        dimension=model.get_sentence_embedding_dimension(),
        load_time_ms=load_time,
    )
    return model


class SentenceTransformerEmbedding:
    """
    CPU-based embedding provider using sentence-transformers.

    ✅ FREE — No API costs
    ✅ OFFLINE — No internet required after model download
    ✅ CPU-COMPATIBLE — Works on machines without GPU
    ✅ FAST — ~50-100ms per batch on CPU
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def _get_model(self) -> "SentenceTransformer":
        """Return the loaded model (lazy-loaded on first call)."""
        return _load_model()

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate a single embedding vector for a text string.

        Args:
            text: Text to embed (query or chunk content).

        Returns:
            List of floats (length = EMBEDDING_DIM = 384).

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for a batch of texts.

        Batching is much more efficient than individual calls.
        Processes up to 32 texts per batch for CPU efficiency.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (each is a list of 384 floats).

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not texts:
            return []

        # Filter out empty strings
        clean_texts = [t.strip() or " " for t in texts]

        start = time.monotonic()
        try:
            model = self._get_model()

            # Run in thread pool to avoid blocking event loop
            import asyncio
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: model.encode(
                    clean_texts,
                    batch_size=32,
                    convert_to_numpy=True,
                    normalize_embeddings=True,  # L2-normalize for cosine similarity
                    show_progress_bar=False,
                ),
            )

            latency_ms = round((time.monotonic() - start) * 1000)
            logger.debug(
                "embedding_batch_complete",
                text_count=len(texts),
                dimension=embeddings.shape[1] if hasattr(embeddings, "shape") else EMBEDDING_DIM,
                latency_ms=latency_ms,
            )

            # Convert numpy array to Python list of lists
            return embeddings.tolist()

        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "embedding_error",
                text_count=len(texts),
                latency_ms=latency_ms,
                error=str(exc),
                exc_info=exc,
            )
            raise EmbeddingError(
                f"Embedding generation failed: {exc}",
                details={"text_count": len(texts)},
            ) from exc

    def get_dimension(self) -> int:
        """Return the embedding dimension."""
        return EMBEDDING_DIM


# Module-level singleton
_embedding_provider: SentenceTransformerEmbedding | None = None


def get_embedding_provider() -> SentenceTransformerEmbedding:
    """
    Return the embedding provider singleton.

    FastAPI dependency or direct call.
    """
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = SentenceTransformerEmbedding()
    return _embedding_provider
