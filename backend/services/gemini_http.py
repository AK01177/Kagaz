"""HTTP calls to Google Gemini with retries, shared by embeddings and chat.

Free-tier keys are rate limited (HTTP 429) and the API has brief outages (5xx), so those are
retried with backoff. Everything else fails fast. Error messages carry only the HTTP status:
response bodies and keys are never logged or raised, because they can echo request content.
"""
from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS = 30.0
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 30.0

_sleep = time.sleep  # replaced in tests


def post_json(
    url: str,
    payload: dict,
    headers: dict[str, str],
    *,
    attempts: int,
    error_cls: type[Exception],
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> httpx.Response:
    """POST `payload`, retrying rate limits, server errors and network failures.

    Raises `error_cls` once attempts are exhausted or on a non-retryable status.
    """
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            if attempt == attempts:
                raise error_cls("The request failed") from exc
            _sleep(backoff_seconds(attempt))
            continue
        if response.status_code == 200:
            return response
        if response.status_code in RETRYABLE_STATUSES and attempt < attempts:
            _sleep(backoff_seconds(attempt, response.headers.get("retry-after")))
            continue
        logger.warning("Gemini request rejected with HTTP %s", response.status_code)
        raise error_cls(f"The service returned HTTP {response.status_code}")
    raise error_cls("The request failed")  # pragma: no cover - the loop always returns or raises


def backoff_seconds(attempt: int, retry_after: str | None = None) -> float:
    """Honour Retry-After when the provider sends it, otherwise back off exponentially."""
    if retry_after:
        try:
            return min(MAX_BACKOFF_SECONDS, max(0.0, float(retry_after)))
        except ValueError:
            pass
    return min(MAX_BACKOFF_SECONDS, 2.0**attempt)
