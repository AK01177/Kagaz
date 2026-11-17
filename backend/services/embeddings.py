"""Text embeddings for policy retrieval (Google Gemini).

Every embedding call goes through this module, so the provider can be replaced
without touching ingestion, retrieval, validation or the assistant.

Behaviour worth knowing:
* Policy chunks use the RETRIEVAL_DOCUMENT task type and questions use
  RETRIEVAL_QUERY; mixing them up measurably lowers retrieval quality.
* Gemini returns un-normalised vectors for reduced dimensions, so every vector is
  L2-normalised here.
* Rate limits and outages are retried by `gemini_http`; the API key travels in a header.
"""
from __future__ import annotations

import math
import os

from app.models.policy import EMBEDDING_DIMENSION
from services.gemini_http import API_BASE, post_json

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
BATCH_SIZE = 100  # the API accepts at most 100 texts per batch request
DOCUMENT_ATTEMPTS = 6  # background-style work can wait out a rate limit
QUERY_ATTEMPTS = 2  # a user is waiting; fail fast and let callers fall back


class EmbeddingServiceError(RuntimeError):
    """The embedding provider is unavailable, misconfigured or returned unusable data."""


def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed policy text chunks (one vector per input, same order)."""
    return _embed(texts, "RETRIEVAL_DOCUMENT", DOCUMENT_ATTEMPTS)


def create_query_embedding(query: str) -> list[float]:
    """Embed a user question used to search policy chunks."""
    return _embed([query], "RETRIEVAL_QUERY", QUERY_ATTEMPTS)[0]


def create_query_embeddings(queries: list[str]) -> list[list[float]]:
    """Embed several search queries in one request (validation searches once per field)."""
    return _embed(queries, "RETRIEVAL_QUERY", DOCUMENT_ATTEMPTS)


def _embed(texts: list[str], task_type: str, attempts: int) -> list[list[float]]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EmbeddingServiceError("Embedding service configuration is missing")
    if any(not text.strip() for text in texts):
        raise EmbeddingServiceError("Cannot embed empty text")

    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        vectors.extend(_embed_batch(batch, task_type, api_key, attempts))
    return vectors


def _embed_batch(batch: list[str], task_type: str, api_key: str, attempts: int) -> list[list[float]]:
    payload = {
        "requests": [
            {
                "model": f"models/{EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "outputDimensionality": EMBEDDING_DIMENSION,
            }
            for text in batch
        ]
    }
    response = post_json(
        f"{API_BASE}/models/{EMBEDDING_MODEL}:batchEmbedContents",
        payload,
        {"x-goog-api-key": api_key},
        attempts=attempts,
        error_cls=EmbeddingServiceError,
    )
    try:
        values = [item["values"] for item in response.json()["embeddings"]]
    except (ValueError, KeyError, TypeError) as exc:
        raise EmbeddingServiceError("Embedding service returned an unreadable response") from exc
    if len(values) != len(batch) or any(len(vector) != EMBEDDING_DIMENSION for vector in values):
        raise EmbeddingServiceError("Embedding service returned an incomplete response")
    return [_normalize(vector) for vector in values]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm < 1e-12:
        raise EmbeddingServiceError("Embedding service returned an empty vector")
    return [value / norm for value in vector]
