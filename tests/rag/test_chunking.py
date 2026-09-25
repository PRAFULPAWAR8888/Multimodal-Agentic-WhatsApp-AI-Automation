import pytest
from whatsapp_agent.rag.chunking.text_splitter import RecursiveTextSplitter

def test_split_short_text_single_chunk():
    splitter = RecursiveTextSplitter(chunk_size=100, chunk_overlap=10)
    text = "This is a short text."
    chunks = splitter.split_text(text)
    assert len(chunks) == 1
    assert chunks[0].content == text
    assert chunks[0].chunk_index == 0

def test_split_long_text_multiple_chunks():
    # Make chunk_size small (in tokens) to force splits
    # chunk_size = 5 tokens ~ 20 characters
    splitter = RecursiveTextSplitter(chunk_size=5, chunk_overlap=1)
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = splitter.split_text(text)
    assert len(chunks) > 1
    assert all(c.chunk_index == i for i, c in enumerate(chunks))

def test_overlap_preserved():
    splitter = RecursiveTextSplitter(chunk_size=10, chunk_overlap=5)
    # chunk_size=10 tokens ~ 40 chars, overlap ~ 20 chars
    text = "Word1 Word2 Word3 Word4 Word5 Word6 Word7 Word8 Word9 Word10"
    chunks = splitter.split_text(text)
    if len(chunks) > 1:
        # Just ensure no words are lost, showing overlap logic didn't drop things
        for word in text.split():
            assert word in "".join(c.content for c in chunks)

def test_empty_text_returns_empty():
    splitter = RecursiveTextSplitter()
    assert splitter.split_text("") == []

def test_metadata_attached_to_chunks():
    splitter = RecursiveTextSplitter(chunk_size=10, chunk_overlap=2)
    metadata = {"source": "test.txt", "page": 1}
    text = "Some random long text to force splitting into multiple parts. " * 10
    chunks = splitter.split_text(text, metadata=metadata)
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.metadata == metadata
        assert chunk.metadata is not metadata  # should be a copy

def test_chunk_indices_sequential():
    splitter = RecursiveTextSplitter(chunk_size=5, chunk_overlap=1)
    text = "A very long text that will definitely be split into several pieces to check indices."
    chunks = splitter.split_text(text)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
