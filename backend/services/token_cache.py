"""Optional Redis cache for validated Supabase tokens.

Without it, every API request makes a network call to Supabase (about 1 s). With REDIS_URL set,
the validated user is kept for a short time, keyed by a hash of the token. If REDIS_URL is unset
or Redis is down, requests simply validate against Supabase as before.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_CACHE_TTL_SECONDS", "60"))
_client = None


def get_redis():
    """Return a shared Redis client, or None when REDIS_URL is not set."""
    global _client
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    if _client is None:
        import redis

        _client = redis.Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
    return _client


def _key(token: str) -> str:
    return "kagaz:token:" + hashlib.sha256(token.encode()).hexdigest()


def get_cached_user(token: str) -> Optional[dict]:
    try:
        client = get_redis()
        raw = client.get(_key(token)) if client else None
        return json.loads(raw) if raw else None
    except Exception:
        logger.warning("Token cache read failed; validating with Supabase", exc_info=True)
        return None


def cache_user(token: str, user: dict) -> None:
    try:
        client = get_redis()
        if client:
            client.setex(_key(token), TOKEN_TTL_SECONDS, json.dumps(user))
    except Exception:
        logger.warning("Token cache write failed", exc_info=True)
