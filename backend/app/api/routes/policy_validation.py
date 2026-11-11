"""Document policy validation API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_policy_reader
from app.db.session import get_db
from app.models.document import Document
from app.schemas.policy_validation import PolicyValidationRunResponse
from services.policy_validation import run_policy_validation

router = APIRouter(prefix="/api/documents", tags=["policy-validation"])


@router.post("/{document_id}/validate-policy", response_model=PolicyValidationRunResponse)
def validate_document_policy(
    document_id: str,
    identity: dict = Depends(require_policy_reader),
    db: Session = Depends(get_db),
):
    if db is None:
        raise HTTPException(503, detail={"code": "DATABASE_UNAVAILABLE", "message": "Policy validation requires the database."})
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == identity["organization_id"],
    ).first()
    if document is None:
        raise HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document not found."})
    run = run_policy_validation(db, document, identity)
    return PolicyValidationRunResponse(
        id=run.id,
        document_id=run.document_id,
        status=run.status,
        summary=run.summary,
        retrieval_outcome=run.retrieval_outcome,
        policy_versions=run.policy_versions,
        findings=[
            {
                "id": finding.id,
                "status": finding.status,
                "requirement": finding.requirement,
                "explanation": finding.explanation,
                "field_name": finding.field_name,
                "document_value": finding.document_value,
                "confidence": finding.confidence,
                "sources": finding.source_references,
            }
            for finding in run.findings
        ],
        created_at=run.created_at,
    )
