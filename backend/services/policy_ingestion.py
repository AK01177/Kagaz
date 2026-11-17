"""Policy ingestion: turn a policy version into searchable, organization-scoped chunks.

Two entry points share one indexing core:
* `ingest_policy_version`    - an uploaded PDF / DOCX / TXT file stored as a Document.
* `index_text_policy_version` - policy text entered through the text policy API.

A version is only made ACTIVE after every step succeeded, in one transaction, so readers
never see a half-indexed policy. Any failure leaves the version FAILED with a short,
user-safe message, and the previously ACTIVE version keeps serving.
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.policy import (
    EMBEDDING_DIMENSION,
    Policy,
    PolicyChunk,
    PolicyVersion,
    PolicyVersionStatus,
)
from services.embeddings import EMBEDDING_MODEL, EmbeddingServiceError, create_embeddings
from services.policy_chunking import ChunkDraft, chunk_policy, chunk_text
from services.policy_text import PolicyTextError, extract_policy_pages
from storage.document_storage import DocumentNotFoundError, DocumentStorage

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _fail(db: Session, version: PolicyVersion, message: str) -> int:
    # Persist a concise status message without copying document text or provider details into logs.
    version.status = PolicyVersionStatus.FAILED
    version.ingestion_error = message
    version.finished_at = _utc_now()
    db.commit()
    return 0


def _guarded(db: Session, version: PolicyVersion, work: Callable[[], int]) -> int:
    """Run `work`; on an unexpected error record it so the version stays visible and retryable."""
    version_id = version.id
    try:
        return work()
    except Exception:
        # Undo any partial chunk writes before recording the failure in a fresh transaction.
        db.rollback()
        try:
            failed_version = db.query(PolicyVersion).filter_by(id=version_id).one()
            return _fail(db, failed_version, "Policy ingestion failed unexpectedly.")
        except Exception:
            db.rollback()
            # A database outage can prevent recording status; avoid logging document or provider data.
            logger.error("Could not record unexpected policy ingestion failure")
            raise


def ingest_policy_version(
    db: Session,
    policy: Policy,
    version: PolicyVersion,
    source_filename: str,
    storage: DocumentStorage,
    *,
    expected_organization_id: Optional[str] = None,
) -> int:
    """Index an uploaded policy file. Returns the number of chunks (0 when it failed)."""
    return _guarded(
        db,
        version,
        lambda: _ingest_uploaded_file(
            db, policy, version, source_filename, storage, expected_organization_id
        ),
    )


def index_text_policy_version(db: Session, policy: Policy, version: PolicyVersion) -> int:
    """Index a text-entered policy version. Returns the number of chunks (0 when it failed)."""
    return _guarded(db, version, lambda: _index_text(db, policy, version))


def index_pending_text_versions(db: Session, policy: Policy) -> None:
    """Index every text-entered version still waiting to be indexed, oldest first."""
    pending = [
        version
        for version in reversed(policy.versions)  # `versions` is newest first
        if version.status == PolicyVersionStatus.PROCESSING and version.source_document_id is None
    ]
    for version in pending:
        index_text_policy_version(db, policy, version)


def _ingest_uploaded_file(
    db: Session,
    policy: Policy,
    version: PolicyVersion,
    source_filename: str,
    storage: DocumentStorage,
    expected_organization_id: Optional[str],
) -> int:
    """Verify organization boundaries, read the file and index it."""
    policy_org = (policy.organization_id or "").strip()
    if not policy_org:
        return _fail(db, version, "Policy ingestion rejected: missing organization context.")
    if expected_organization_id is not None and policy_org != str(expected_organization_id).strip():
        return _fail(db, version, "Policy ingestion rejected: organization context mismatch.")
    if version.policy_id != policy.id:
        return _fail(db, version, "Policy ingestion rejected: policy version mismatch.")

    source_doc = db.query(Document).filter(Document.id == version.source_document_id).first()
    if source_doc is None or source_doc.organization_id != policy_org:
        return _fail(
            db,
            version,
            "Policy ingestion rejected: source document does not belong to policy organization.",
        )

    try:
        pages = extract_policy_pages(storage.resolve(version.source_document_id))
    except (PolicyTextError, DocumentNotFoundError, OSError):
        return _fail(db, version, "Policy text extraction failed.")
    if not pages:
        return _fail(db, version, "No readable text was extracted from the policy file.")
    return _index_version(db, policy, version, chunk_policy(pages), source_filename)


def _index_text(db: Session, policy: Policy, version: PolicyVersion) -> int:
    if not (policy.organization_id or "").strip():
        return _fail(db, version, "Policy ingestion rejected: missing organization context.")
    if version.policy_id != policy.id:
        return _fail(db, version, "Policy ingestion rejected: policy version mismatch.")
    return _index_version(db, policy, version, chunk_text(version.content or ""), None)


def _index_version(
    db: Session,
    policy: Policy,
    version: PolicyVersion,
    drafts: list[ChunkDraft],
    source_filename: Optional[str],
) -> int:
    """Embed the chunks, replace the version's chunks and activate it atomically."""
    if not drafts:
        return _fail(db, version, "No readable text was extracted from the policy.")

    hashes = [_content_hash(draft.content) for draft in drafts]
    try:
        vectors = _vectors_for(db, policy, version, drafts, hashes)
    except EmbeddingServiceError:
        return _fail(db, version, "Policy embeddings could not be generated.")

    # Reject incomplete provider responses before any write.
    if len(vectors) != len(drafts) or any(len(vector) != EMBEDDING_DIMENSION for vector in vectors):
        return _fail(db, version, "The embedding service returned invalid vectors.")

    db.query(PolicyChunk).filter(PolicyChunk.policy_version_id == version.id).delete(
        synchronize_session=False
    )
    # Keep source and tenant identifiers with each chunk for audit and retrieval traceability.
    for index, (draft, content_hash, vector) in enumerate(zip(drafts, hashes, vectors)):
        db.add(
            PolicyChunk(
                policy_version_id=version.id,
                content=draft.content,
                content_hash=content_hash,
                embedding=vector,
                chunk_index=index,
                page_number=draft.page_number,
                section=draft.section,
                chunk_metadata={
                    "chunk_index": index,
                    "organization_id": policy.organization_id,
                    "policy_id": policy.id,
                    "policy_name": policy.name,
                    "policy_version_id": version.id,
                    "version": version.version,
                    "domain": policy.domain,
                    "document_type": policy.document_type,
                    "source_document_id": version.source_document_id,
                    "source_filename": source_filename,
                },
            )
        )

    # Archive first, then activate in the same transaction so readers see one complete active version.
    # The partial unique index also prevents two active versions for one policy.
    db.query(PolicyVersion).filter(
        PolicyVersion.policy_id == policy.id,
        PolicyVersion.status == PolicyVersionStatus.ACTIVE,
    ).update({PolicyVersion.status: PolicyVersionStatus.ARCHIVED}, synchronize_session=False)
    db.flush()
    version.status = PolicyVersionStatus.ACTIVE
    version.embedding_model = EMBEDDING_MODEL
    version.ingestion_error = None
    version.finished_at = _utc_now()
    version.published_at = version.finished_at
    policy.current_version = version.version
    db.commit()
    return len(drafts)


def _vectors_for(
    db: Session,
    policy: Policy,
    version: PolicyVersion,
    drafts: list[ChunkDraft],
    hashes: list[str],
) -> list[list[float]]:
    """One vector per draft, calling the embedding API only for clauses not seen before.

    A new version of the same policy usually changes a few clauses. Unchanged clauses
    reuse the vector stored for the identical text (same policy, same embedding model),
    which keeps ingestion fast and within the provider's rate limits.
    """
    known = _stored_vectors(db, policy, version, set(hashes))
    missing = [draft.content for draft, content_hash in zip(drafts, hashes) if content_hash not in known]
    if missing:
        for content, vector in zip(missing, create_embeddings(missing)):
            known[_content_hash(content)] = vector
    if any(content_hash not in known for content_hash in hashes):
        return []  # the provider returned fewer vectors than requested; the caller rejects this
    return [known[content_hash] for content_hash in hashes]


def _stored_vectors(
    db: Session, policy: Policy, version: PolicyVersion, hashes: set[str]
) -> dict[str, list[float]]:
    rows = (
        db.query(PolicyChunk.content_hash, PolicyChunk.embedding)
        .join(PolicyVersion, PolicyVersion.id == PolicyChunk.policy_version_id)
        .filter(
            PolicyVersion.policy_id == policy.id,
            PolicyVersion.id != version.id,
            PolicyVersion.embedding_model == EMBEDDING_MODEL,
            PolicyChunk.content_hash.in_(hashes),
        )
        .all()
    )
    return {content_hash: [float(value) for value in embedding] for content_hash, embedding in rows}


def reindex_stale_versions(db: Session, storage: DocumentStorage) -> dict[str, int]:
    """Re-embed ACTIVE versions whose vectors came from another (or an unknown) embedding model.

    Retrieval ignores such versions, so after changing the embedding model this is what
    brings a policy back. Returns {policy_version_id: chunk_count}; 0 means that version failed.
    """
    stale = (
        db.query(PolicyVersion, Policy)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .filter(
            PolicyVersion.status == PolicyVersionStatus.ACTIVE,
            or_(PolicyVersion.embedding_model.is_(None), PolicyVersion.embedding_model != EMBEDDING_MODEL),
        )
        .all()
    )
    results: dict[str, int] = {}
    for version, policy in stale:
        version_id = version.id
        version.status = PolicyVersionStatus.PROCESSING
        db.commit()
        if version.source_document_id is None:
            results[version_id] = index_text_policy_version(db, policy, version)
            continue
        source = db.get(Document, version.source_document_id)
        filename = source.filename if source else ""
        results[version_id] = ingest_policy_version(
            db, policy, version, filename, storage, expected_organization_id=policy.organization_id
        )
    return results
