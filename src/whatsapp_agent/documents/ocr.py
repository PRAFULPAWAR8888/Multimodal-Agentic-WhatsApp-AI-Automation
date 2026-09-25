"""
PaddleOCR Provider for Document Text Extraction.

Extracts dense text (receipts, invoices, documents) from images.
Runs locally and efficiently on CPU.
"""

from __future__ import annotations

import io
import time
from functools import lru_cache

from PIL import Image
from whatsapp_agent.core.exceptions import VisionError
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _load_paddleocr():
    """Lazy-load the PaddleOCR model."""
    try:
        from paddleocr import PaddleOCR
        import logging
        
        # Suppress verbose paddle logs
        logging.getLogger("ppocr").setLevel(logging.ERROR)
        
        logger.info("loading_paddleocr_model")
        start = time.monotonic()
        
        # use_angle_cls=True to automatically rotate images
        # lang="en" for English (can be extended)
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        
        logger.info("paddleocr_model_loaded", latency_ms=round((time.monotonic() - start) * 1000))
        return ocr
        
    except ImportError as exc:
        raise VisionError("paddleocr is not installed. Run: pip install paddleocr paddlepaddle") from exc


class PaddleOCRProvider:
    """Local OCR provider using PaddleOCR."""

    def __init__(self) -> None:
        pass

    async def extract_text(self, image_bytes: bytes) -> str:
        """
        Extract text from an image.
        
        Args:
            image_bytes: Raw JPEG/PNG image bytes.
            
        Returns:
            Extracted text as a single string, with lines separated by newlines.
        """
        if not image_bytes:
            raise VisionError("Empty image bytes provided for OCR.")

        start = time.monotonic()
        
        try:
            # We run it synchronously here since PaddleOCR is heavily optimized with numpy/C++,
            # but ideally this should be run in a thread pool via run_in_executor to avoid blocking.
            import asyncio
            import numpy as np
            
            loop = asyncio.get_event_loop()
            
            # Helper to run in thread
            def _run_ocr():
                # Convert bytes to numpy array for PaddleOCR
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img_array = np.array(image)
                
                ocr = _load_paddleocr()
                result = ocr.ocr(img_array, cls=True)
                
                # Result format: [[[[x,y],...], (text, confidence)], ...]
                extracted_lines = []
                if result and result[0]:
                    for line in result[0]:
                        text = line[1][0]
                        extracted_lines.append(text)
                        
                return "\n".join(extracted_lines)

            text = await loop.run_in_executor(None, _run_ocr)
            
            latency_ms = round((time.monotonic() - start) * 1000)
            logger.info("paddleocr_extraction_complete", latency_ms=latency_ms, text_length=len(text))
            
            return text
            
        except Exception as exc:
            logger.error("paddleocr_extraction_error", error=str(exc), exc_info=exc)
            raise VisionError(f"OCR extraction failed: {exc}") from exc


# Module-level singleton
_ocr_provider: PaddleOCRProvider | None = None

def get_ocr_provider() -> PaddleOCRProvider:
    """Return the PaddleOCR provider singleton."""
    global _ocr_provider
    if _ocr_provider is None:
        _ocr_provider = PaddleOCRProvider()
    return _ocr_provider
