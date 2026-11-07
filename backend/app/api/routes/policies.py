import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_policy_reader
from app.db.session import get_db
from app.schemas.policy import PolicyEvidence, PolicyRetrievalRequest, PolicyRetrievalResponse
from services.policy_retrieval import (
    EmbeddingServiceError,
    create_query_embedding,
    retrieve_policy_evidence,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("/retrieve", response_model=PolicyRetrievalResponse)
def retrieve(
    request: PolicyRetrievalRequest,
    identity: dict = Depends(require_policy_reader),
    db: Session = Depends(get_db),
):
    try:
        embedding = create_query_embedding(request.query)
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "EMBEDDING_UNAVAILABLE", "message": str(exc)},
        ) from exc

    result = retrieve_policy_evidence(
        db,
        identity["organization_id"],
        identity["role"],
        request.query,
        embedding,
        request.domain,
        request.document_type,
        request.limit,
    )
    logger.info(
        "policy_retrieval organization_id=%s user_id=%s outcome=%s",
        identity["organization_id"],
        identity["sub"],
        result.outcome,
    )
    if result.outcome != "results":
        return PolicyRetrievalResponse(
            outcome=result.outcome,
            message="No policy evidence met the requested filters and relevance threshold.",
        )

    return PolicyRetrievalResponse(
        outcome="results",
        results=[
            PolicyEvidence(
                policy_id=policy.id,
                version=version.version,
                score=float(score),
                content=chunk.content,
                page_number=chunk.page_number,
                section=chunk.section,
                chunk_index=chunk.chunk_index,
                metadata=chunk.chunk_metadata,
                source_document_id=version.source_document_id,
                source_filename=document.filename,
            )
            for policy, version, chunk, score, document in result.rows
        ],
    )
