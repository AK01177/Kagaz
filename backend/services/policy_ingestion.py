"""PDF policy ingestion into the existing organization-scoped vector store."""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.policy import (
    EMBEDDING_DIMENSION,
    Policy,
    PolicyChunk,
    PolicyVersion,
    PolicyVersionStatus,
)
from services.extraction import ExtractionError, extract_text
from services.policy_retrieval import EmbeddingServiceError, create_embeddings
from storage.document_storage import DocumentStorage


CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def chunk_policy_text(text: str) -> list[str]:
    """Split text into overlapping, ordered chunks without dropping content."""
    text = text.strip()
    if not text:
        return []

    # Overlap preserves context for sentences that cross a chunk boundary.
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary
        content = text[start:end].strip()
        if content:
            chunks.append(content)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


def _fail(db: Session, version: PolicyVersion, message: str) -> int:
    # Persist a concise status message without copying document text or provider details into logs.
    version.status = PolicyVersionStatus.FAILED
    version.ingestion_error = message
    version.finished_at = _utc_now()
    db.commit()
    return 0


def ingest_policy_version(
    db: Session,
    policy: Policy,
    version: PolicyVersion,
    source_filename: str,
    storage: DocumentStorage,
    *,
    expected_organization_id: Optional[str] = None,
) -> int:
    """Record unexpected processing errors so this version remains visible and retryable."""
    version_id = version.id
    try:
        return _process_policy_version(
            db,
            policy,
            version,
            source_filename,
            storage,
            expected_organization_id=expected_organization_id,
        )
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


def _process_policy_version(
    db: Session,
    policy: Policy,
    version: PolicyVersion,
    source_filename: str,
    storage: DocumentStorage,
    *,
    expected_organization_id: Optional[str] = None,
) -> int:
    """Verify organization boundaries, extract, embed and atomically activate a policy version."""
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
        # Reuse the document extraction service so scanned PDFs take its OCR fallback path.
        text = extract_text(version.source_document_id, storage)
    except (ExtractionError, OSError):
        return _fail(db, version, "Policy text extraction failed.")

    chunks = chunk_policy_text(text)
    if not chunks:
        return _fail(db, version, "No readable text was extracted from the PDF.")

    try:
        embeddings = create_embeddings(chunks)
    except EmbeddingServiceError:
        return _fail(db, version, "Policy embeddings could not be generated.")

    # Match the database vector column and reject incomplete provider responses before writes.
    if len(embeddings) != len(chunks) or any(
        len(embedding) != EMBEDDING_DIMENSION for embedding in embeddings
    ):
        return _fail(db, version, "The embedding service returned invalid vectors.")

    db.query(PolicyChunk).filter(
        PolicyChunk.policy_version_id == version.id
    ).delete(synchronize_session=False)
    # Keep source and tenant identifiers with each chunk for audit and retrieval traceability.
    for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
        db.add(
            PolicyChunk(
                policy_version_id=version.id,
                content=content,
                embedding=embedding,
                chunk_index=index,
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
    ).update(
        {PolicyVersion.status: PolicyVersionStatus.ARCHIVED},
        synchronize_session=False,
    )
    db.flush()
    version.status = PolicyVersionStatus.ACTIVE
    version.ingestion_error = None
    version.finished_at = _utc_now()
    version.published_at = version.finished_at
    db.commit()
    return len(chunks)
