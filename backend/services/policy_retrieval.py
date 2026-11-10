import os
from dataclasses import dataclass, field

from app.models.document import Document
from sqlalchemy.orm import Session
from sqlalchemy import or_

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


def create_embeddings(texts: list[str]) -> list[list[float]]:
    global _openai_client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EmbeddingServiceError("Embedding service configuration is missing")
    try:
        from openai import APIError, OpenAI

        if _openai_client is None:
            _openai_client = OpenAI(api_key=api_key, timeout=10.0)
        embeddings: list[list[float]] = []
        for offset in range(0, len(texts), 100):
            # Batch chunks to limit request size while using the same model as retrieval.
            batch = texts[offset : offset + 100]
            response = _openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
            )
            # The API returns an input index; restore input order before pairing vectors with chunks.
            embeddings.extend(
                item.embedding for item in sorted(response.data, key=lambda item: item.index)
            )
        if len(embeddings) != len(texts):
            raise EmbeddingServiceError("Embedding service returned an incomplete response")
        return embeddings
    except ImportError as exc:
        raise EmbeddingServiceError("The OpenAI client dependency is not installed") from exc
    except (APIError, ValueError, RuntimeError) as exc:
        raise EmbeddingServiceError("Embedding generation failed") from exc


def create_query_embedding(query: str) -> list[float]:
    """Keep query embedding on the same provider/model path as policy chunks."""
    return create_embeddings([query])[0]


@dataclass(frozen=True)
class RetrievalResult:
    outcome: str
    rows: list
    incomplete_policies: list[dict] = field(default_factory=list)


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
        Policy.is_active.is_(True),
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
        Policy.is_active.is_(True),
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


def retrieve_policy_validation_corpus(
    db: Session,
    organization_id: str,
    role: str,
    embedding: list[float],
    document_type: str | None,
    limit: int,
) -> RetrievalResult:
    """Return the complete active, readable policy scope for validation when it fits.

    Unlike interactive search, validation must not silently omit relevant clauses
    because they fell outside a top-k or similarity threshold. The bounded result
    lets callers fail closed and request human review if the whole scope is too large.
    Policies without a document_type are treated as organization-wide policies.
    """
    distance = PolicyChunk.embedding.cosine_distance(embedding)
    normalized_role = (role or "").strip().upper()
    allowed_classifications = [PolicyClassification.PUBLIC, PolicyClassification.INTERNAL]
    for classification, roles in CLASSIFICATION_ROLES.items():
        if roles is None or normalized_role in roles:
            allowed_classifications.append(classification)

    filters = [
        Policy.organization_id == organization_id,
        Policy.is_active.is_(True),
        Document.organization_id == organization_id,
        PolicyVersion.status == PolicyVersionStatus.ACTIVE,
        Policy.classification.in_(allowed_classifications),
    ]
    normalized_type = document_type.strip() if document_type and document_type.strip() else None
    if normalized_type is None:
        filters.append(Policy.document_type.is_(None))
    else:
        filters.append(or_(Policy.document_type == normalized_type, Policy.document_type.is_(None)))

    policy_scope = [
        Policy.organization_id == organization_id,
        Policy.is_active.is_(True),
        Policy.classification.in_(allowed_classifications),
    ]
    if normalized_type is None:
        policy_scope.append(Policy.document_type.is_(None))
    else:
        policy_scope.append(or_(Policy.document_type == normalized_type, Policy.document_type.is_(None)))

    scoped_policies = db.query(Policy.id, Policy.name, Policy.current_version).filter(*policy_scope).all()
    indexed_policy_ids = {
        row[0]
        for row in (
            db.query(Policy.id)
            .join(PolicyVersion, PolicyVersion.policy_id == Policy.id)
            .join(PolicyChunk, PolicyChunk.policy_version_id == PolicyVersion.id)
            .join(Document, Document.id == PolicyVersion.source_document_id)
            .filter(*filters)
            .distinct()
            .all()
        )
    }
    incomplete_policies = [
        {"policy_id": policy_id, "policy_name": name, "version": current_version}
        for policy_id, name, current_version in scoped_policies
        if policy_id not in indexed_policy_ids
    ]
    if incomplete_policies:
        return RetrievalResult("unindexed_policy_evidence", [], incomplete_policies)

    candidates = (
        db.query(Policy, PolicyVersion, PolicyChunk, (1 - distance).label("score"), Document)
        .join(PolicyVersion, PolicyVersion.policy_id == Policy.id)
        .join(PolicyChunk, PolicyChunk.policy_version_id == PolicyVersion.id)
        .join(Document, Document.id == PolicyVersion.source_document_id)
        .filter(*filters)
        .order_by(distance)
        .limit(limit + 1)
        .all()
    )
    if len(candidates) > limit:
        return RetrievalResult("scope_too_large", candidates[:limit])
    if not candidates:
        return RetrievalResult("no_results", [])
    return RetrievalResult("results", candidates)
