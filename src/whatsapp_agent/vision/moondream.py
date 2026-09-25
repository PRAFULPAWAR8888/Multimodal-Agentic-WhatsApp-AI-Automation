"""
Moondream2 Vision Language Model Provider.

Uses the tiny but powerful 'vikhyatk/moondream2' model to understand images.
Since this is a 1.8B parameter model, it can run on CPU reasonably well.
"""

from __future__ import annotations

import io
import time
from functools import lru_cache

from PIL import Image
from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import VisionError
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _load_moondream():
    """Lazy-load the moondream2 model and processor."""
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
    except ImportError as exc:
        raise VisionError("transformers/torch not installed. Run: pip install transformers torch torchvision") from exc

    settings = get_settings()
    model_id = settings.moondream_model

    logger.info("loading_moondream_model", model_id=model_id)
    start = time.monotonic()
    
    try:
        # Load model with trust_remote_code=True (required for moondream2)
        # Using CPU here. 
        model = AutoModelForCausalLM.from_pretrained(
            model_id, trust_remote_code=True
        ).to("cpu")
        
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        
        logger.info("moondream_model_loaded", latency_ms=round((time.monotonic() - start) * 1000))
        return model, tokenizer
        
    except Exception as exc:
        raise VisionError(f"Failed to load moondream model: {exc}") from exc


class MoondreamProvider:
    """Local VLM provider using moondream2."""

    def __init__(self) -> None:
        pass

    async def describe_image(self, image_bytes: bytes, prompt: str = "Describe this image in detail.") -> str:
        """
        Generate a description of the image.
        
        Args:
            image_bytes: Raw JPEG/PNG image bytes.
            prompt: Question or prompt about the image.
            
        Returns:
            The model's textual response.
        """
        if not image_bytes:
            raise VisionError("Empty image bytes provided for vision processing.")

        start = time.monotonic()
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            
            def _run_moondream():
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                model, tokenizer = _load_moondream()
                
                # Encapsulate the image
                enc_image = model.encode_image(image)
                # Answer the question
                answer = model.answer_question(enc_image, prompt, tokenizer)
                return answer

            description = await loop.run_in_executor(None, _run_moondream)
            
            latency_ms = round((time.monotonic() - start) * 1000)
            logger.info("moondream_description_complete", latency_ms=latency_ms)
            
            return description
            
        except Exception as exc:
            logger.error("moondream_description_error", error=str(exc), exc_info=exc)
            raise VisionError(f"Vision description failed: {exc}") from exc


# Module-level singleton
_moondream_provider: MoondreamProvider | None = None

def get_vision_provider() -> MoondreamProvider:
    """Return the Moondream provider singleton."""
    global _moondream_provider
    if _moondream_provider is None:
        _moondream_provider = MoondreamProvider()
    return _moondream_provider
