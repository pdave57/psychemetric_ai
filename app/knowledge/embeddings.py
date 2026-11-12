"""Embedding generation interface and mock/portable generator."""

import math
import hashlib
from typing import List


def generate_embedding(text: str, dim: int = 1536) -> List[float]:
    """Generate a deterministic normalized embedding vector.

    In production with an OpenAI key, this can call text-embedding-3-small.
    Here it provides a portable, deterministic vector representation for
    reproducible search and test stability.
    """
    if not text:
        return [0.0] * dim

    # Generate pseudo-dense vector from sha256 hash digests of text slices
    vec = []
    text_bytes = text.encode("utf-8")
    for i in range(dim):
        h = hashlib.sha256(text_bytes + i.to_bytes(2, "little")).digest()
        # Convert first 4 bytes to float in range [-1.0, 1.0]
        val = (int.from_bytes(h[:4], "little") / 0xFFFFFFFF) * 2.0 - 1.0
        vec.append(val)

    # L2-normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]
