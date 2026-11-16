import base64
import time
from typing import Any

from openai import OpenAI
from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import VisionError
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

class QwenProvider:
    """Vision Provider using Qwen API via xkiro.com."""

    def __init__(self) -> None:
        settings = get_settings()
        if not getattr(settings, "qwen_api_key", ""):
            raise VisionError("QWEN_API_KEY is not set.")
        self.client = OpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
        )
        self.model = settings.qwen_model

    async def describe_image(
        self, image_bytes: bytes, prompt: str = "Analyze this image and describe the objects you see."
    ) -> str:
        """
        Generate a description of the image using the Qwen model.

        Args:
            image_bytes: Raw image bytes.
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

            def _call_qwen() -> str:
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                mime_type = "image/jpeg"
                if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                    mime_type = "image/png"
                elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:16]:
                    mime_type = "image/webp"

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{base64_image}"
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=500,
                )
                return response.choices[0].message.content or ""

            description = await loop.run_in_executor(None, _call_qwen)

            latency_ms = round((time.monotonic() - start) * 1000)
            logger.info("qwen_description_complete", latency_ms=latency_ms)

            return description

        except Exception as exc:
            logger.error("qwen_description_error", error=str(exc), exc_info=exc)
            raise VisionError(f"Vision description failed: {exc}") from exc
