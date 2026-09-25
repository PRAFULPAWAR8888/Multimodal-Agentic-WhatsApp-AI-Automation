import io
import pdfplumber
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

async def extract_pdf_text(document_bytes: bytes) -> str:
    """Extract text from a PDF document using pdfplumber."""
    try:
        import asyncio
        loop = asyncio.get_event_loop()

        def _extract():
            text = []
            with pdfplumber.open(io.BytesIO(document_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
            return "\n".join(text)

        extracted_text = await loop.run_in_executor(None, _extract)
        return extracted_text
    except Exception as e:
        logger.error("pdf_extraction_failed", error=str(e))
        return ""
