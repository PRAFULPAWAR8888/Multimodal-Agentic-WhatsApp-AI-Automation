"""
Document loaders for different source types.

Each loader extracts raw text from a specific document format.
Supported: PDF, plain text, Markdown, CSV
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
import io
import csv

@dataclass
class LoadedDocument:
    """Raw extracted text from a document."""
    content: str
    metadata: dict[str, Any]
    source_uri: str
    mime_type: str
    page_count: int | None = None
    word_count: int = 0

class PDFLoader:
    """
    Load text from PDF files using pdfplumber.
    
    pdfplumber is better than PyMuPDF for text-heavy PDFs.
    Falls back to PyMuPDF (pymupdf) if pdfplumber fails.
    """
    async def load_bytes(self, pdf_bytes: bytes, source_uri: str) -> LoadedDocument:
        """Load PDF from bytes and extract all text."""
        import pdfplumber
        
        text = []
        page_count = 0
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text.append(extracted)
        except Exception:
            # Fallback to PyMuPDF
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)
            for page in doc:
                text.append(page.get_text())
            doc.close()
            
        full_text = "\n".join(text)
        word_count = len(full_text.split())
        
        return LoadedDocument(
            content=full_text,
            metadata={"source": source_uri, "page_count": page_count},
            source_uri=source_uri,
            mime_type="application/pdf",
            page_count=page_count,
            word_count=word_count
        )
    
    async def load_file(self, file_path: Path) -> LoadedDocument:
        """Load PDF from file path."""
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        return await self.load_bytes(pdf_bytes, str(file_path))

class TextLoader:
    """Load plain text or Markdown files."""
    async def load_bytes(self, text_bytes: bytes, source_uri: str, mime_type: str = "text/plain") -> LoadedDocument:
        text = text_bytes.decode("utf-8", errors="replace")
        word_count = len(text.split())
        return LoadedDocument(
            content=text,
            metadata={"source": source_uri},
            source_uri=source_uri,
            mime_type=mime_type,
            word_count=word_count
        )

class CSVLoader:
    """
    Load CSV files, converting rows to readable text.
    Format: 'Column1: value1, Column2: value2, ...'
    """
    async def load_bytes(self, csv_bytes: bytes, source_uri: str) -> LoadedDocument:
        text = csv_bytes.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        
        lines = []
        for row in reader:
            line = ", ".join([f"{k}: {v}" for k, v in row.items() if k and v])
            lines.append(line)
            
        full_text = "\n".join(lines)
        word_count = len(full_text.split())
        
        return LoadedDocument(
            content=full_text,
            metadata={"source": source_uri},
            source_uri=source_uri,
            mime_type="text/csv",
            word_count=word_count
        )

def get_loader_for_mime_type(mime_type: str):
    """Return the appropriate loader for a MIME type."""
    loaders = {
        "application/pdf": PDFLoader(),
        "text/plain": TextLoader(),
        "text/markdown": TextLoader(),
        "text/csv": CSVLoader(),
    }
    return loaders.get(mime_type, TextLoader())
