"""Centralized append-only audit event recording and safe metadata sanitization."""
from __future__ import annotations

import itertools
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.workflow import AuditEvent

logger = logging.getLogger(__name__)

_SEQUENCE_LOCK = threading.Lock()
_SEQUENCE_COUNTER = itertools.count(1)

_BLOCKED_METADATA_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "api_key",
    "apikey",
    "authorization",
    "auth_header",
    "cookie",
    "credentials",
    "credential",
    "private_key",
    "ocr_text",
    "raw_text",
    "document_text",
    "content",
    "extracted_fields",
    "field_values",
    "file_bytes",
    "raw_bytes",
    "prompt",
    "raw_response",
    "excerpt",
    "body",
}

_SECRET_VALUE_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
    re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"),
)


def _next_sequence_no() -> int:
    with _SEQUENCE_LOCK:
        return next(_SEQUENCE_COUNTER)


def sanitize_audit_text(value: Optional[str], *, max_length: int = 512) -> Optional[str]:
    """Redact secret-like tokens and bound length before persisting audit text."""
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    for pattern in _SECRET_VALUE_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "..."
    return cleaned


def _sanitize_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return sanitize_audit_text(value, max_length=256)
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(item, depth=depth + 1) for item in list(value)[:50]]
    if isinstance(value, dict):
        return sanitize_audit_metadata(value, _depth=depth + 1)
    return sanitize_audit_text(str(value), max_length=256)


def sanitize_audit_metadata(
    raw_details: Optional[dict[str, Any]],
    *,
    _depth: int = 0,
) -> dict[str, Any]:
    """Strip secret keys and bulky/unnecessary document contents from audit metadata."""
    if not raw_details or not isinstance(raw_details, dict) or _depth > 4:
        return {}

    sanitized: dict[str, Any] = {}
    for key, val in raw_details.items():
        key_str = str(key).strip()
        lowered = key_str.lower()
        if lowered in _BLOCKED_METADATA_KEYS or any(
            sensitive in lowered
            for sensitive in ("secret", "password", "token", "api_key", "apikey", "private_key", "ocr_text", "document_text")
        ):
            continue
        sanitized[key_str] = _sanitize_value(val, depth=_depth)
    return sanitized


def build_audit_event(
    *,
    document_id: str,
    organization_id: str,
    event_type: str,
    actor_id: str,
    actor_role: str,
    actor_type: str = "USER",
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    decision: Optional[str] = None,
    reason: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    created_at: Optional[datetime] = None,
) -> AuditEvent:
    """Construct a sanitized append-only AuditEvent ORM instance."""
    normalized_actor_type = "SYSTEM" if str(actor_type).upper() == "SYSTEM" else "USER"
    resolved_actor_id = (str(actor_id).strip() or ("system" if normalized_actor_type == "SYSTEM" else "unknown"))[:64]
    resolved_role = (str(actor_role).strip() or ("SYSTEM" if normalized_actor_type == "SYSTEM" else "USER"))[:64]

    return AuditEvent(
        document_id=str(document_id),
        organization_id=str(organization_id),
        event_type=str(event_type).strip().upper()[:64],
        actor_id=resolved_actor_id,
        actor_type=normalized_actor_type,
        actor_role=resolved_role,
        from_status=str(from_status) if from_status is not None else None,
        to_status=str(to_status) if to_status is not None else None,
        decision=str(decision) if decision is not None else None,
        reason=sanitize_audit_text(reason),
        details=sanitize_audit_metadata(details),
        sequence_no=_next_sequence_no(),
        created_at=created_at or datetime.now(timezone.utc),
    )


def record_audit_event(
    db: Optional[Session],
    *,
    document_id: str,
    organization_id: str,
    event_type: str,
    actor_id: str,
    actor_role: str,
    actor_type: str = "USER",
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    decision: Optional[str] = None,
    reason: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    created_at: Optional[datetime] = None,
    commit: bool = True,
    ensure_document_exists: bool = False,
) -> Optional[AuditEvent]:
    """Persist an append-only AuditEvent cleanly with optional transaction ownership."""
    if db is None:
        return None

    if ensure_document_exists:
        exists = db.query(Document.id).filter(Document.id == str(document_id)).first()
        if exists is None:
            return None

    event = build_audit_event(
        document_id=document_id,
        organization_id=organization_id,
        event_type=event_type,
        actor_id=actor_id,
        actor_role=actor_role,
        actor_type=actor_type,
        from_status=from_status,
        to_status=to_status,
        decision=decision,
        reason=reason,
        details=details,
        created_at=created_at,
    )
    db.add(event)
    if commit:
        try:
            db.commit()
            db.refresh(event)
        except Exception:
            db.rollback()
            raise
    return event


def record_extraction_audit(
    db: Optional[Session],
    *,
    document_id: str,
    organization_id: str,
    document_type: Optional[str],
    field_names: list[str],
    actor_id: str = "system",
    actor_type: str = "SYSTEM",
    actor_role: str = "SYSTEM",
    from_status: Optional[str] = None,
    to_status: str = "EXTRACTED",
    ocr_text_length: Optional[int] = None,
    commit: bool = False,
    ensure_document_exists: bool = False,
) -> Optional[AuditEvent]:
    """Record structured field extraction without storing extracted field values or raw OCR text."""
    details: dict[str, Any] = {
        "document_type": document_type,
        "field_count": len(field_names),
        "field_names": sorted(field_names),
    }
    if ocr_text_length is not None:
        details["ocr_text_length"] = ocr_text_length

    return record_audit_event(
        db,
        document_id=document_id,
        organization_id=organization_id,
        event_type="EXTRACTION_COMPLETED",
        actor_id=actor_id,
        actor_type=actor_type,
        actor_role=actor_role,
        from_status=from_status,
        to_status=to_status,
        details=details,
        commit=commit,
        ensure_document_exists=ensure_document_exists,
    )
