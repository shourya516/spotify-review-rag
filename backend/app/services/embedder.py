"""
Embedding service.

Generates vector embeddings for review text using the OpenAI
text-embedding-3-small model (1536 dims).

Batch processing is used to stay within API rate limits, with
exponential-backoff retries via tenacity.
"""
from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from openai import RateLimitError, APIError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[OpenAI] = None

EMBED_BATCH_SIZE = 100   # OpenAI allows up to 2048 inputs per request


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


@retry(
    retry=retry_if_exception_type((RateLimitError, APIError)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Call the OpenAI embeddings API for a batch of texts.
    Retries automatically on rate limit or transient API errors.
    """
    client = _get_client()
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.

    Splits into batches of EMBED_BATCH_SIZE to respect API limits.
    Returns a list of float vectors in the same order as input.
    """
    if not texts:
        return []

    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        logger.info(
            "Embedding batch %d-%d of %d",
            i + 1,
            min(i + EMBED_BATCH_SIZE, len(texts)),
            len(texts),
        )
        embeddings = _embed_batch(batch)
        all_embeddings.extend(embeddings)

    return all_embeddings


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    result = _embed_batch([query])
    return result[0]
