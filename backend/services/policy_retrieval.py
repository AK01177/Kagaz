import os
from dataclasses import dataclass

from app.models.document import Document
from sqlalchemy.orm import Session

from app.models.policy import (
    Policy,
    PolicyClassification,
    PolicyChunk,
    PolicyVersion,
    PolicyVersionStatus,
)


RELEVANCE_THRESHOLD = float(os.getenv("POLICY_RELEVANCE_THRESHOLD", "0.75"))
EMBEDDING_MODEL = "text-embedding-3-small"
_openai_client = None
REVIEWER_ROLES = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN", "COMPLIANCE", "AUDITOR"}
CLASSIFICATION_ROLES = {
    PolicyClassification.PUBLIC: None,
    PolicyClassification.INTERNAL: None,
    PolicyClassification.REVIEWER_ONLY: REVIEWER_ROLES,
    PolicyClassification.CONFIDENTIAL: {"ORG_ADMIN", "SYSTEM_ADMIN", "COMPLIANCE", "AUDITOR"},
    PolicyClassification.RESTRICTED: {"ORG_ADMIN", "SYSTEM_ADMIN"},
}


class EmbeddingServiceError(RuntimeError):
    pass


def create_query_embedding(query: str) -> list[float]:
    global _openai_client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EmbeddingServiceError("Embedding service configuration is missing")
    try:
        from openai import APIError, OpenAI

        if _openai_client is None:
            _openai_client = OpenAI(api_key=api_key, timeout=10.0)
        response = _openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query,
        )
        return response.data[0].embedding
    except ImportError as exc:
        raise EmbeddingServiceError("The OpenAI client dependency is not installed") from exc
    except (APIError, ValueError, RuntimeError) as exc:
        raise EmbeddingServiceError("Embedding generation failed") from exc


@dataclass(frozen=True)
class RetrievalResult:
    outcome: str
    rows: list


def retrieve_policy_evidence(
    db: Session,
    organization_id: str,
    role: str,
    embedding: list[float],
    domain: str | None,
    document_type: str | None,
    policy_version: str | None,
    limit: int,
) -> RetrievalResult:
    distance = PolicyChunk.embedding.cosine_distance(embedding)
    score = (1 - distance).label("score")
    normalized_role = (role or "").strip().upper()
    filters = [
        Policy.organization_id == organization_id,
        Document.organization_id == organization_id,
        distance <= (1 - RELEVANCE_THRESHOLD),
    ]
    if policy_version is None:
        filters.append(PolicyVersion.status == PolicyVersionStatus.ACTIVE)
    if domain is not None:
        filters.append(Policy.domain == domain)
    if document_type is not None:
        filters.append(Policy.document_type == document_type.strip())
    if policy_version is not None:
        filters.append(PolicyVersion.version == policy_version.strip())

    allowed_classifications = [
        PolicyClassification.PUBLIC,
        PolicyClassification.INTERNAL,
    ]
    for classification, roles in CLASSIFICATION_ROLES.items():
        if roles is None or normalized_role in roles:
            allowed_classifications.append(classification)

    eligible_filters = [
        Policy.organization_id == organization_id,
        Document.organization_id == organization_id,
        Policy.classification.in_(allowed_classifications),
    ]
    if policy_version is None:
        eligible_filters.append(PolicyVersion.status == PolicyVersionStatus.ACTIVE)
    if domain is not None:
        eligible_filters.append(Policy.domain == domain)
    if document_type is not None:
        eligible_filters.append(Policy.document_type == document_type.strip())
    if policy_version is not None:
        eligible_filters.append(PolicyVersion.version == policy_version.strip())

    candidates = (
        db.query(Policy, PolicyVersion, PolicyChunk, score, Document)
        .join(PolicyVersion, PolicyVersion.policy_id == Policy.id)
        .join(PolicyChunk, PolicyChunk.policy_version_id == PolicyVersion.id)
        .join(Document, Document.id == PolicyVersion.source_document_id)
        .filter(*filters)
        .filter(Policy.classification.in_(allowed_classifications))
        .order_by(distance)
        .limit(limit)
        .all()
    )
    if not candidates:
        any_candidates = (
            db.query(PolicyChunk.id)
            .join(PolicyVersion, PolicyVersion.id == PolicyChunk.policy_version_id)
            .join(Policy, Policy.id == PolicyVersion.policy_id)
            .join(Document, Document.id == PolicyVersion.source_document_id)
            .filter(*eligible_filters)
            .first()
        )
        return RetrievalResult("low_relevance" if any_candidates else "no_results", [])
    return RetrievalResult("results", candidates)
