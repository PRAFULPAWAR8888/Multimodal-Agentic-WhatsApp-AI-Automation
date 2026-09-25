"""
Text chunking for RAG ingestion.

Splits documents into overlapping chunks for embedding.
Uses recursive character splitting strategy.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class DocumentChunkData:
    """A single text chunk ready for embedding."""
    content: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

class RecursiveTextSplitter:
    """
    Recursively splits text into chunks with overlap.
    
    Strategy: Try to split on paragraphs first, then sentences, then words.
    This preserves semantic meaning better than fixed-size splitting.
    
    Default config (optimized for RAG):
    - chunk_size: 512 tokens (~400 words)
    - chunk_overlap: 64 tokens (~50 words)
    - separators: ["\n\n", "\n", ". ", " ", ""]
    """
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        separators: list[str] | None = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text: str, metadata: dict[str, Any] | None = None) -> list[DocumentChunkData]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full document text to split.
            metadata: Optional metadata to attach to each chunk (e.g. page_number, source).
        
        Returns:
            List of DocumentChunkData ordered by chunk_index.
        """
        if not text:
            return []
        
        final_chunks = self._split_recursive(text, self.separators)
        
        merged_chunks = self._merge_splits(final_chunks, separator="")
        
        results = []
        meta = metadata or {}
        for i, chunk in enumerate(merged_chunks):
            if chunk.strip():
                results.append(DocumentChunkData(
                    content=chunk,
                    chunk_index=i,
                    metadata=meta.copy()
                ))
        return results
    
    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if not separators:
            # If no separators left, split by chunk_size characters (fallback)
            return [text[i:i+self.chunk_size*4] for i in range(0, len(text), self.chunk_size*4)]
        
        separator = separators[0]
        if separator:
            splits = self._split_with_separator(text, separator)
        else:
            splits = list(text) # Character by character
        
        final_splits = []
        for s in splits:
            if self._token_count(s) <= self.chunk_size:
                final_splits.append(s)
            else:
                if separator:
                    sub_splits = self._split_recursive(s, separators[1:])
                    final_splits.extend(sub_splits)
                else:
                    # chunk is single char, shouldn't happen, but just append
                    final_splits.append(s)
        return final_splits
    
    def _split_with_separator(self, text: str, separator: str) -> list[str]:
        """Split text by separator, keeping separator."""
        if not separator:
            return list(text)
        splits = text.split(separator)
        return [s + separator if i < len(splits) - 1 else s for i, s in enumerate(splits) if s or i == len(splits) - 1]
    
    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        """Merge small splits up to chunk_size with overlap."""
        docs = []
        current_doc = []
        total = 0
        for s in splits:
            _len = self._token_count(s)
            if total + _len > self.chunk_size and current_doc:
                docs.append("".join(current_doc))
                # Now we need to pop from current_doc until total <= chunk_size - chunk_overlap
                while total > self.chunk_overlap and current_doc:
                    popped = current_doc.pop(0)
                    total -= self._token_count(popped)
            current_doc.append(s)
            total += _len
        if current_doc:
            docs.append("".join(current_doc))
        return docs
    
    def _token_count(self, text: str) -> int:
        """Estimate token count (4 chars ≈ 1 token)."""
        return max(1, len(text) // 4)
