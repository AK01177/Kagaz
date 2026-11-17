"""JSON chat completions for policy validation and the assistant (Google Gemini).

Uses Gemini's OpenAI-compatible endpoint with JSON mode and temperature 0, so the same
question gives the same answer. Retries for rate limits and outages are handled by
`gemini_http`. Callers treat `LLMServiceError` as "the model is unavailable" and fall back
to a safe, deterministic result instead of guessing.
"""
from __future__ import annotations

import json
import os
import re

from services.gemini_http import API_BASE, post_json

LLM_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite")
CHAT_URL = f"{API_BASE}/openai/chat/completions"
REQUEST_TIMEOUT_SECONDS = 60.0
ATTEMPTS = 3

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class LLMServiceError(RuntimeError):
    """The language model is unavailable, misconfigured or returned unusable output."""


def llm_is_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def chat_json(system: str, user: str) -> dict:
    """Ask the model for a JSON object and return it parsed."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise LLMServiceError("Language model configuration is missing")
    response = post_json(
        CHAT_URL,
        {
            "model": LLM_MODEL,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        {"Authorization": f"Bearer {api_key}"},
        attempts=ATTEMPTS,
        error_cls=LLMServiceError,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    try:
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(_CODE_FENCE.sub("", content.strip()))
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMServiceError("The language model returned an unreadable response") from exc
    if not isinstance(parsed, dict):
        raise LLMServiceError("The language model did not return a JSON object")
    return parsed
