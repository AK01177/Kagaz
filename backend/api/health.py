import os

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import engine
from services.token_cache import get_redis
from storage.s3_document_storage import get_document_storage

router = APIRouter()


@router.get("/api/health")
def health_check():
    """Liveness: the process is up. Used by Docker and Render, so it never touches other services."""
    return {"status": "ok"}


def _check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _check_redis() -> str:
    client = get_redis()
    if client is None:
        return "not configured"
    client.ping()
    return "ok"


def _check_storage() -> str:
    storage = get_document_storage()
    client = getattr(storage, "client", None)
    bucket = getattr(storage, "bucket", None)
    if client is None or bucket is None:
        return "local disk"
    client.head_bucket(Bucket=bucket)
    return "ok"


def _check_supabase() -> None:
    response = httpx.get(
        os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/health",
        headers={"apikey": os.environ["SUPABASE_ANON_KEY"]},
        timeout=3.0,
    )
    response.raise_for_status()


@router.get("/api/health/ready")
def readiness_check():
    """Readiness: every service the API depends on answers. Returns 503 if any one does not."""
    checks = {}
    for name, check in (
        ("database", _check_database),
        ("redis", _check_redis),
        ("storage", _check_storage),
        ("supabase", _check_supabase),
    ):
        try:
            checks[name] = check() or "ok"
        except Exception as exc:
            checks[name] = f"failed: {type(exc).__name__}"
    healthy = all(not str(v).startswith("failed") for v in checks.values())
    return JSONResponse(status_code=200 if healthy else 503,
                        content={"status": "ready" if healthy else "unavailable", "checks": checks})
