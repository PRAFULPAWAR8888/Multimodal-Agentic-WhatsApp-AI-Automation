"""
Faster-Whisper Speech-to-Text Provider.

Transcribes WhatsApp voice messages (OGG/Opus audio) to text.

Why faster-whisper:
- 4x faster than openai-whisper on CPU
- Uses CTranslate2 for optimized inference
- int8 quantization for minimal memory usage (~150MB for 'base' model)
- Free, open-source (MIT license)
- Excellent multilingual support (99 languages, including Hindi, Marathi, Tamil)
- Auto language detection

Model sizes (CPU speed / accuracy tradeoff):
- tiny:   ~39M params, ~32MB RAM, fastest
- base:   ~74M params, ~145MB RAM, good balance ← DEFAULT
- small:  ~244M params, ~461MB RAM, better accuracy
- medium: ~769M params, ~1.5GB RAM, high accuracy (may be slow on 8GB RAM)
- large:  ~1.5B params, ~3GB RAM, best quality (NOT recommended for 8GB RAM)

Config via .env:
    FASTER_WHISPER_MODEL=base
    FASTER_WHISPER_DEVICE=cpu
    FASTER_WHISPER_COMPUTE_TYPE=int8
    FASTER_WHISPER_LANGUAGE=  (empty = auto-detect)
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import STTError
from whatsapp_agent.observability.logging import get_logger

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = get_logger(__name__)


@dataclass
class TranscriptionResult:
    """Result of a speech-to-text transcription."""

    text: str
    language: str
    language_probability: float
    duration_seconds: float
    segments: list[dict]
    latency_ms: int


@lru_cache(maxsize=1)
def _load_whisper_model() -> "WhisperModel":
    """
    Load and cache the faster-whisper model.

    Called once on first transcription. Subsequent calls return the cached model.
    Loading takes 2-5 seconds on CPU.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise STTError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    settings = get_settings()
    model_size = settings.faster_whisper_model
    device = settings.faster_whisper_device
    compute_type = settings.faster_whisper_compute_type

    logger.info(
        "loading_whisper_model",
        model=model_size,
        device=device,
        compute_type=compute_type,
    )
    start = time.monotonic()

    # Set to cpu for CPU-only machines
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        num_workers=2,  # Parallel decoding threads
        cpu_threads=os.cpu_count() or 4,
    )

    load_time_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "whisper_model_loaded",
        model=model_size,
        device=device,
        load_time_ms=load_time_ms,
    )
    return model


class FasterWhisperSTT:
    """
    CPU-based Speech-to-Text using faster-whisper.

    ✅ FREE — No API costs
    ✅ OFFLINE — No internet required after model download
    ✅ CPU-COMPATIBLE — Works without GPU (int8 quantization)
    ✅ MULTILINGUAL — Auto-detects Hindi, Marathi, English, Tamil, etc.
    ✅ FAST — ~5-10x real-time on modern CPU (base model)
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def _get_model(self) -> "WhisperModel":
        """Return the loaded model (lazy-loaded on first call)."""
        return _load_whisper_model()

    async def transcribe_bytes(
        self,
        audio_bytes: bytes,
        language: str | None = None,
        audio_format: str = "ogg",
    ) -> TranscriptionResult:
        """
        Transcribe audio from bytes.

        WhatsApp voice notes are OGG/Opus format. This method handles them directly.

        Args:
            audio_bytes: Raw audio file bytes (OGG/Opus, MP3, WAV, etc.).
            language: Force language (e.g. 'hi' for Hindi). None = auto-detect.
            audio_format: Audio format hint ('ogg', 'mp3', 'wav', 'm4a').

        Returns:
            TranscriptionResult with text, detected language, and metadata.

        Raises:
            STTError: If transcription fails.
        """
        if not audio_bytes:
            raise STTError("Empty audio bytes provided for transcription.")

        # Write to temp file (faster-whisper requires file path or numpy array)
        suffix = f".{audio_format}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return await self._transcribe_file(Path(tmp_path), language=language)
        finally:
            # Always clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _transcribe_file(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> TranscriptionResult:
        """
        Transcribe an audio file from disk.

        Runs in a thread pool to avoid blocking the async event loop.
        faster-whisper is CPU-bound — blocking would freeze all concurrent requests.

        Args:
            audio_path: Path to the audio file.
            language: Force language code (None = auto-detect).

        Returns:
            TranscriptionResult.
        """
        forced_language = language or self._settings.faster_whisper_language or None

        logger.info(
            "whisper_transcribing",
            audio_path=str(audio_path),
            forced_language=forced_language,
        )
        start = time.monotonic()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._run_transcription(audio_path, forced_language),
            )

            latency_ms = round((time.monotonic() - start) * 1000)
            result.latency_ms = latency_ms

            logger.info(
                "whisper_transcription_complete",
                language=result.language,
                language_prob=round(result.language_probability, 3),
                duration_seconds=round(result.duration_seconds, 1),
                text_length=len(result.text),
                latency_ms=latency_ms,
            )
            return result

        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "whisper_transcription_error",
                audio_path=str(audio_path),
                latency_ms=latency_ms,
                error=str(exc),
                exc_info=exc,
            )
            raise STTError(
                f"Transcription failed: {exc}",
                details={"audio_path": str(audio_path)},
            ) from exc

    def _run_transcription(
        self,
        audio_path: Path,
        language: str | None,
    ) -> TranscriptionResult:
        """
        Run transcription synchronously (called from thread pool).

        Returns raw TranscriptionResult (latency_ms set to 0, filled in caller).
        """
        model = self._get_model()

        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            vad_filter=True,         # Voice Activity Detection — removes silence
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=400,
            ),
            word_timestamps=False,    # Not needed for basic transcription
        )

        # Collect all segments
        segment_list = []
        full_text_parts = []
        for segment in segments:
            segment_list.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            })
            full_text_parts.append(segment.text.strip())

        full_text = " ".join(full_text_parts).strip()

        return TranscriptionResult(
            text=full_text,
            language=info.language,
            language_probability=info.language_probability,
            duration_seconds=info.duration,
            segments=segment_list,
            latency_ms=0,  # Filled in by async wrapper
        )


# Module-level singleton
_stt_provider: FasterWhisperSTT | None = None


def get_stt_provider() -> FasterWhisperSTT:
    """Return the faster-whisper STT provider singleton."""
    global _stt_provider
    if _stt_provider is None:
        _stt_provider = FasterWhisperSTT()
    return _stt_provider
