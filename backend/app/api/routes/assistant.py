"""
API routes for Document and Policy Assistant (BE-14).

Provides protected endpoint to ask grounded questions about accessible
documents and their applicable policies.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import Permission, require_permission
from app.db.session import get_db
from app.schemas.assistant import AssistantQueryRequest, AssistantQueryResponse
from services.assistant import query_document_assistant

router = APIRouter(prefix="/api/documents", tags=["assistant"])


def _require_db(db: Optional[Session]) -> Session:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database connection is required for the document assistant.",
            },
        )
    return db


@router.post(
    "/{document_id}/assistant/query",
    response_model=AssistantQueryResponse,
    summary="Query the document and policy assistant",
)
@router.post(
    "/{document_id}/assistant",
    response_model=AssistantQueryResponse,
    summary="Query the document and policy assistant (alias)",
)
def query_assistant_endpoint(
    document_id: str,
    body: AssistantQueryRequest,
    actor: Annotated[dict, Depends(require_permission(Permission.ASSISTANT_QUERY))],
    db: Annotated[Optional[Session], Depends(get_db)] = None,
) -> AssistantQueryResponse:
    """
    Ask a question about an accessible document and applicable organization policies.

    Enforces organization isolation and user authorization. Returns grounded
    factual answers with source references. The assistant cannot make workflow decisions.
    """
    session = _require_db(db)
    return query_document_assistant(
        session,
        document_id=document_id,
        question=body.question,
        actor=actor,
    )
