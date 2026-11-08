"""
CRUD operations for BE-09 Document Validation.
Provides persistence and retrieval of document validation results.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.validation import ValidationResult


def save_validation_result(
    db: Session,
    document_id: str,
    organization_id: str,
    status: str,
    policy_id: Optional[str] = None,
    policy_version: Optional[str] = None,
    issues: Optional[List[dict]] = None,
    evidence: Optional[List[dict]] = None,
    validated_by: Optional[str] = None,
) -> ValidationResult:
    """Upsert validation outcome for a document."""
    record = db.query(ValidationResult).filter(ValidationResult.document_id == document_id).first()
    if record is None:
        record = ValidationResult(
            document_id=document_id,
            organization_id=organization_id,
        )
        db.add(record)

    record.organization_id = organization_id
    record.status = status
    record.policy_id = policy_id
    record.policy_version = policy_version
    record.issues = issues or []
    record.evidence = evidence or []
    record.validated_by = validated_by
    record.validated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(record)
    return record


def get_validation_result(
    db: Session,
    document_id: str,
    organization_id: Optional[str] = None,
) -> Optional[ValidationResult]:
    """Fetch stored validation result, enforcing organization isolation when requested."""
    query = db.query(ValidationResult).filter(ValidationResult.document_id == document_id)
    if organization_id:
        query = query.filter(ValidationResult.organization_id == organization_id)
    return query.first()
