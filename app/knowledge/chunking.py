"""Text chunking utilities for RAG ingestion."""

from typing import List, Dict, Any


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks with character and word bounds.

    Returns a list of dicts with 'chunk_index' and 'content'.
    """
    if not text:
        return []

    words = text.split()
    chunks = []
    start = 0
    chunk_index = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_content = " ".join(words[start:end])
        chunks.append({
            "chunk_index": chunk_index,
            "content": chunk_content,
        })
        chunk_index += 1
        if end == len(words):
            break
        start += max(1, chunk_size - overlap)

    return chunks
