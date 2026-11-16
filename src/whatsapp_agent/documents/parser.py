import io
import asyncio
from typing import Optional
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


async def extract_pdf_text(document_bytes: bytes) -> str:
    """
    Extract text from a PDF document.
    Uses pdfplumber first, falling back to PyMuPDF (fitz) if needed.
    """
    if not document_bytes:
        return ""

    loop = asyncio.get_event_loop()

    def _extract() -> str:
        text = []
        # Attempt 1: pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(document_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text.strip())
        except Exception as e:
            logger.debug("pdfplumber_failed_falling_back_to_pymupdf", error=str(e))

        result = "\n\n".join(text).strip()
        if len(result) >= 50:
            return result

        # Attempt 2: PyMuPDF (fitz) fallback
        try:
            import fitz
            doc = fitz.open(stream=document_bytes, filetype="pdf")
            pymupdf_text = []
            for page in doc:
                p_text = page.get_text()
                if p_text:
                    pymupdf_text.append(p_text.strip())
            doc.close()
            fallback_result = "\n\n".join(pymupdf_text).strip()
            if fallback_result:
                return fallback_result
        except Exception as e:
            logger.debug("pymupdf_fallback_failed", error=str(e))

        return result

    try:
        return await loop.run_in_executor(None, _extract)
    except Exception as e:
        logger.error("pdf_extraction_failed", error=str(e))
        return ""


async def extract_docx_text(document_bytes: bytes) -> str:
    """Extract text from a Word (.docx) document."""
    if not document_bytes:
        return ""

    loop = asyncio.get_event_loop()

    def _extract() -> str:
        try:
            import docx
            doc = docx.Document(io.BytesIO(document_bytes))
            parts = []
            for p in doc.paragraphs:
                if p.text.strip():
                    parts.append(p.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        parts.append(row_text)
            return "\n".join(parts)
        except Exception as e:
            logger.error("docx_extraction_failed", error=str(e))
            return ""

    try:
        return await loop.run_in_executor(None, _extract)
    except Exception as e:
        logger.error("docx_extraction_failed", error=str(e))
        return ""


async def extract_document_text(
    document_bytes: bytes,
    filename: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> str:
    """
    Intelligently extract text from any supported document format (PDF, DOCX, TXT, CSV).
    """
    fname = (filename or "").lower()
    mime = (mime_type or "").lower()

    if fname.endswith(".docx") or "wordprocessingml" in mime:
        return await extract_docx_text(document_bytes)
    elif fname.endswith(".pdf") or "pdf" in mime or document_bytes.startswith(b"%PDF"):
        return await extract_pdf_text(document_bytes)
    elif fname.endswith(".txt") or fname.endswith(".md") or fname.endswith(".csv") or "text" in mime:
        try:
            return document_bytes.decode("utf-8", errors="replace")
        except Exception:
            return ""
    else:
        # Default try PDF then DOCX
        if document_bytes.startswith(b"%PDF"):
            return await extract_pdf_text(document_bytes)
        try:
            return await extract_docx_text(document_bytes)
        except Exception:
            return document_bytes.decode("utf-8", errors="replace")

