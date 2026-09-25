"""
Piper Text-to-Speech Provider.

Generates native WhatsApp Voice Notes from text using local CPU inference.

Why Piper TTS:
- 10-20x faster than real-time on standard CPUs
- Very high quality voices (VITS models)
- Local and free
- Low latency (supports streaming, though we use file-based generation here)

Process:
1. Synthesize text to WAV via `piper` subprocess.
2. Convert WAV to OGG/Opus via `ffmpeg` subprocess.
   WhatsApp STRICTLY requires `audio/ogg; codecs=opus` for voice notes.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import TTSError
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


class PiperTTSProvider:
    """Local TTS provider using Piper and FFmpeg."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._model_path = self._settings.piper_model_path

    async def _run_subprocess(self, cmd: list[str], input_data: bytes | None = None) -> bytes:
        """Run a subprocess asynchronously and return stdout."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if input_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(input=input_data)

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore')
            logger.error("subprocess_failed", cmd=cmd[0], error=error_msg)
            raise TTSError(f"Command {' '.join(cmd)} failed: {error_msg}")

        return stdout

    async def generate_voice_note(self, text: str) -> bytes:
        """
        Generate an OGG/Opus voice note from text.

        1. Runs Piper to generate a WAV file.
        2. Runs FFmpeg to convert WAV to OGG/Opus.

        Args:
            text: The text to synthesize.

        Returns:
            Raw bytes of the generated OGG/Opus audio file.
        """
        if not text.strip():
            raise TTSError("Empty text provided for TTS.")

        logger.info("tts_generation_started", text_length=len(text))
        start_time = time.monotonic()

        # Temporary files for processing
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file, \
             tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_file:
            
            wav_path = wav_file.name
            ogg_path = ogg_file.name

        try:
            # 1. Synthesize WAV using Piper
            # Command: piper --model <model_path> --output_file <wav_path>
            # Input text is passed via stdin
            cmd_piper = [
                "piper",
                "--model",
                str(self._model_path),
                "--output_file",
                wav_path,
            ]
            
            try:
                await self._run_subprocess(cmd_piper, input_data=text.encode('utf-8'))
            except TTSError as exc:
                # Add context to the error if piper isn't found or model is missing
                if not self._model_path.exists():
                    raise TTSError(f"Piper model not found at {self._model_path}. Please download it.") from exc
                raise exc
            except FileNotFoundError:
                raise TTSError("piper executable not found in PATH. Please install piper-tts.")

            piper_latency = round((time.monotonic() - start_time) * 1000)
            logger.debug("piper_synthesis_complete", latency_ms=piper_latency)

            # 2. Convert WAV to OGG/Opus using FFmpeg
            # Command: ffmpeg -y -i <wav_path> -c:a libopus -b:a 24k -v warning <ogg_path>
            cmd_ffmpeg = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-i", wav_path,
                "-c:a", "libopus",
                "-b:a", "24k",  # Low bitrate is sufficient for voice
                "-v", "warning", # Less verbose output
                ogg_path,
            ]
            
            try:
                await self._run_subprocess(cmd_ffmpeg)
            except FileNotFoundError:
                raise TTSError("ffmpeg executable not found in PATH. Please install ffmpeg.")

            # Read the final OGG bytes
            with open(ogg_path, "rb") as f:
                ogg_bytes = f.read()

            total_latency = round((time.monotonic() - start_time) * 1000)
            logger.info(
                "tts_generation_complete",
                latency_ms=total_latency,
                audio_size_bytes=len(ogg_bytes)
            )

            return ogg_bytes

        finally:
            # Cleanup temp files
            for p in (wav_path, ogg_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

# Module-level singleton
_tts_provider: PiperTTSProvider | None = None

def get_tts_provider() -> PiperTTSProvider:
    """Return the Piper TTS provider singleton."""
    global _tts_provider
    if _tts_provider is None:
        _tts_provider = PiperTTSProvider()
    return _tts_provider
