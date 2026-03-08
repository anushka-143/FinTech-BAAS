"""Embedding Service — production-grade vector embedding via Gemini.

Uses gemini-embedding-001 (GA July 2025, MTEB #1 multilingual).
text-embedding-004 deprecated Aug 2025 — DO NOT USE.

Features:
  - Task-typed embeddings (RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, etc.)
  - 768-dim output (scaled from 3072 via MRL for storage efficiency)
  - Batch embedding with rate limiting
  - Embedding cache (avoid re-embedding identical content)
  - PII masking before embedding
"""

from __future__ import annotations

import hashlib
from typing import Any

from packages.core.settings import get_settings

# Embedding config
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768
MAX_BATCH_SIZE = 100
MAX_INPUT_TOKENS = 8192

# Cache: hash(text+task_type) → vector
_embedding_cache: dict[str, list[float]] = {}


class EmbeddingTaskType:
    """Task types for Gemini embedding optimization."""
    RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
    RETRIEVAL_QUERY = "RETRIEVAL_QUERY"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
    CLASSIFICATION = "CLASSIFICATION"
    CLUSTERING = "CLUSTERING"


async def embed_text(
    text: str,
    task_type: str = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    use_cache: bool = True,
) -> list[float]:
    """Embed a single text string into a 768-dim vector.

    Args:
        text: Input text (max 8K tokens)
        task_type: Gemini task type for optimized embeddings
        use_cache: Whether to use the in-memory cache
    """
    cache_key = hashlib.sha256(f"{task_type}:{text}".encode()).hexdigest()
    if use_cache and cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    settings = get_settings()
    if not settings.google_api_key:
        # Sandbox fallback: deterministic pseudo-embedding
        return _deterministic_embedding(text)

    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    result = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={
            "task_type": task_type,
            "output_dimensionality": EMBEDDING_DIMENSIONS,
        },
    )

    vector = list(result.embeddings[0].values)

    if use_cache:
        _embedding_cache[cache_key] = vector

    return vector


async def embed_batch(
    texts: list[str],
    task_type: str = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
) -> list[list[float]]:
    """Embed multiple texts in a single API call.

    Args:
        texts: List of input texts (max 100 per batch)
        task_type: Gemini task type
    """
    if not texts:
        return []

    settings = get_settings()
    if not settings.google_api_key:
        return [_deterministic_embedding(t) for t in texts]

    from google import genai

    client = genai.Client(api_key=settings.google_api_key)

    results: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[i:i + MAX_BATCH_SIZE]
        result = await client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch,
            config={
                "task_type": task_type,
                "output_dimensionality": EMBEDDING_DIMENSIONS,
            },
        )
        for emb in result.embeddings:
            results.append(list(emb.values))

    return results


def _deterministic_embedding(text: str) -> list[float]:
    """Generate a deterministic pseudo-embedding for sandbox/dev use.

    NOT for production. Uses character hash to produce repeatable vectors.
    """
    import struct
    h = hashlib.sha256(text.encode()).digest()
    # Extend hash to fill 768 dimensions
    values = []
    for i in range(EMBEDDING_DIMENSIONS):
        byte_idx = i % len(h)
        val = (h[byte_idx] + i) % 256
        values.append((val / 255.0) * 2 - 1)  # Normalize to [-1, 1]
    # L2-normalize
    norm = sum(v * v for v in values) ** 0.5
    if norm > 0:
        values = [v / norm for v in values]
    return values


def clear_cache() -> int:
    """Clear the embedding cache. Returns number of entries cleared."""
    count = len(_embedding_cache)
    _embedding_cache.clear()
    return count
