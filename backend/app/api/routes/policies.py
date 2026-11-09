import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.auth import require_policy_admin, require_policy_reader
from api.upload_limit import UploadLimitRoute
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.policy import (
    Policy,
    PolicyClassification,
    PolicyVersion,
    PolicyVersionStatus,
)
from app.schemas.policy import (
    PolicyEvidence,
    PolicyIngestionResponse,
    PolicyRetrievalRequest,
    PolicyRetrievalResponse,
    PolicyVersionSummary,
)
from services.policy_ingestion import ingest_policy_version
from services.policy_retrieval import (
    EmbeddingServiceError,
    create_query_embedding,
    retrieve_policy_evidence,
)
from services.upload import CHUNK_BYTES, MAX_UPLOAD_BYTES, UploadError, _validate_pdf
from storage.document_storage import DocumentStorage


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/policies",
    tags=["policies"],
    route_class=UploadLimitRoute,
)


def _ingestion_response(
    policy: Policy,
    version: PolicyVersion,
    source: Document,
    chunk_count: int,
) -> PolicyIngestionResponse:
    return PolicyIngestionResponse(
        policy_id=policy.id,
        policy_version_id=version.id,
        source_document_id=source.id,
        source_filename=source.filename,
        version=version.version,
        status=version.status.value,
        chunk_count=chunk_count,
        ingestion_error=version.ingestion_error,
    )


def _ingest_uploaded_policy(
    file: UploadFile,
    policy_name: str,
    version_name: str,
    domain: str | None,
    document_type: str | None,
    classification: PolicyClassification,
    identity: dict,
    db: Session | None,
) -> PolicyIngestionResponse:
    if db is None:
        raise HTTPException(503, detail={
            "code": "DATABASE_UNAVAILABLE",
            "message": "Policy ingestion requires the database.",
        })

    policy_name = policy_name.strip()
    version_name = version_name.strip()
    domain = domain.strip() if domain and domain.strip() else None
    document_type = document_type.strip() if document_type and document_type.strip() else None
    if not policy_name or not version_name:
        raise HTTPException(422, detail={
            "code": "INVALID_POLICY_METADATA",
            "message": "Policy name and version must contain text.",
        })

    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or "\x00" in filename or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(415, detail={
            "code": "UNSUPPORTED_POLICY_FORMAT",
            "message": "Policy files must be PDFs.",
        })

    # Resolve policies only inside the authenticated organization and selected metadata identity.
    policy = db.query(Policy).filter(
        Policy.organization_id == identity["organization_id"],
        Policy.name == policy_name,
        Policy.domain == domain,
        Policy.document_type == document_type,
    ).first()
    if policy is not None:
        existing = db.query(PolicyVersion).filter(
            PolicyVersion.policy_id == policy.id,
            PolicyVersion.version == version_name,
        ).first()
        if existing is not None:
            raise HTTPException(409, detail={
                "code": "POLICY_VERSION_EXISTS",
                "message": "This policy version already exists; retry it if its status is FAILED.",
            })

    # Keep policy files outside the generic document download lookup path.
    storage_root = DocumentStorage()
    storage = DocumentStorage(str(storage_root.base_dir / "policy_sources"))
    storage.base_dir.mkdir(parents=True, exist_ok=True)
    document_id = f"doc_{uuid4().hex}"
    document_path = storage.base_dir / f"{document_id}.pdf"
    size = 0
    try:
        # Validate in a staging directory so rejected uploads never leave a partial source file.
        with TemporaryDirectory(prefix="policy_upload_", dir=storage.base_dir) as staging:
            staged_path = Path(staging) / "policy.pdf"
            with staged_path.open("wb") as destination:
                while chunk := file.file.read(CHUNK_BYTES):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, detail={
                            "code": "FILE_TOO_LARGE",
                            "message": "Maximum file size is 10 MiB.",
                        })
                    destination.write(chunk)
            if size == 0:
                raise HTTPException(400, detail={
                    "code": "INVALID_FILE",
                    "message": "The uploaded PDF is empty.",
                })
            try:
                _validate_pdf(staged_path)
            except UploadError as exc:
                raise HTTPException(exc.status_code, detail={
                    "code": exc.code,
                    "message": str(exc),
                }) from exc
            staged_path.replace(document_path)

        if policy is None:
            policy = Policy(
                organization_id=identity["organization_id"],
                name=policy_name,
                classification=classification,
                domain=domain,
                document_type=document_type,
            )
            db.add(policy)
            db.flush()
        else:
            policy.classification = classification

        # The tenant and uploader always come from the verified token, not the form data.
        source = Document(
            id=document_id,
            organization_id=identity["organization_id"],
            uploaded_by=identity["sub"],
            filename=filename,
            file_type="application/pdf",
            file_size=size,
            storage_path=str(document_path.resolve()),
            status=DocumentStatus.UPLOADED,
        )
        version = PolicyVersion(
            policy_id=policy.id,
            source_document_id=document_id,
            version=version_name,
            status=PolicyVersionStatus.PROCESSING,
        )
        # Commit PROCESSING before extraction so failures remain visible and retryable.
        db.add_all([source, version])
        db.commit()
        db.refresh(policy)
        db.refresh(version)
        db.refresh(source)
    except HTTPException:
        document_path.unlink(missing_ok=True)
        raise
    except Exception:
        db.rollback()
        document_path.unlink(missing_ok=True)
        logger.error("Could not record policy ingestion request")
        raise HTTPException(500, detail={
            "code": "POLICY_INGESTION_RECORD_FAILED",
            "message": "The policy ingestion request could not be recorded.",
        })

    chunk_count = ingest_policy_version(db, policy, version, filename, storage)
    db.refresh(version)
    return _ingestion_response(policy, version, source, chunk_count)


@router.post("/ingest", response_model=PolicyIngestionResponse, status_code=201)
async def ingest(
    file: UploadFile = File(...),
    policy_name: str = Form(..., max_length=255),
    version: str = Form(..., max_length=50),
    domain: str | None = Form(default=None, max_length=100),
    document_type: str | None = Form(default=None, max_length=100),
    classification: PolicyClassification = Form(default=PolicyClassification.INTERNAL),
    identity: dict = Depends(require_policy_admin),
    db: Session | None = Depends(get_db),
):
    """Submit a PDF policy for extraction, chunking and vector indexing."""
    try:
        return await run_in_threadpool(
            _ingest_uploaded_policy,
            file,
            policy_name,
            version,
            domain,
            document_type,
            classification,
            identity,
            db,
        )
    finally:
        await file.close()


@router.get("/{policy_id}/versions", response_model=list[PolicyVersionSummary])
def list_policy_versions(
    policy_id: str,
    identity: dict = Depends(require_policy_admin),
    db: Session = Depends(get_db),
):
    """Show an organization's policy version history and ingestion outcomes."""
    if db is None:
        raise HTTPException(503, detail={
            "code": "DATABASE_UNAVAILABLE",
            "message": "Policy ingestion status is unavailable.",
        })
    policy = db.query(Policy).filter(
        Policy.id == policy_id,
        Policy.organization_id == identity["organization_id"],
    ).first()
    if policy is None:
        raise HTTPException(404, detail={
            "code": "POLICY_NOT_FOUND",
            "message": "Policy not found.",
        })
    versions = (
        db.query(PolicyVersion, Document)
        .join(Document, Document.id == PolicyVersion.source_document_id)
        .filter(PolicyVersion.policy_id == policy.id)
        .order_by(PolicyVersion.created_at.desc())
        .all()
    )
    return [
        PolicyVersionSummary(
            policy_version_id=version.id,
            source_document_id=source.id,
            source_filename=source.filename,
            version=version.version,
            status=version.status.value,
            chunk_count=len(version.chunks),
            ingestion_error=version.ingestion_error,
        )
        for version, source in versions
    ]


@router.post(
    "/{policy_id}/versions/{version_id}/retry",
    response_model=PolicyIngestionResponse,
)
async def retry_policy_version(
    policy_id: str,
    version_id: str,
    identity: dict = Depends(require_policy_admin),
    db: Session = Depends(get_db),
):
    """Reprocess the existing failed version from its stored source PDF."""
    if db is None:
        raise HTTPException(503, detail={
            "code": "DATABASE_UNAVAILABLE",
            "message": "Policy ingestion requires the database.",
        })
    policy = db.query(Policy).filter(
        Policy.id == policy_id,
        Policy.organization_id == identity["organization_id"],
    ).first()
    version = db.query(PolicyVersion).filter(
        PolicyVersion.id == version_id,
        PolicyVersion.policy_id == policy_id,
    ).first() if policy is not None else None
    if policy is None or version is None:
        raise HTTPException(404, detail={
            "code": "POLICY_VERSION_NOT_FOUND",
            "message": "Policy version not found.",
        })
    if version.status != PolicyVersionStatus.FAILED:
        raise HTTPException(409, detail={
            "code": "POLICY_VERSION_NOT_RETRYABLE",
            "message": "Only failed policy versions can be retried.",
        })
    source = db.query(Document).filter(
        Document.id == version.source_document_id,
        Document.organization_id == identity["organization_id"],
    ).first()
    if source is None:
        raise HTTPException(404, detail={
            "code": "POLICY_SOURCE_NOT_FOUND",
            "message": "The source document for this policy version was not found.",
        })

    # Reuse the version record so retries cannot create additional active versions.
    version.status = PolicyVersionStatus.PROCESSING
    version.ingestion_error = None
    version.finished_at = None
    db.commit()
    storage_root = DocumentStorage()
    storage = DocumentStorage(str(storage_root.base_dir / "policy_sources"))
    chunk_count = await run_in_threadpool(
        ingest_policy_version,
        db,
        policy,
        version,
        source.filename,
        storage,
    )
    db.refresh(version)
    return _ingestion_response(policy, version, source, chunk_count)


@router.post("/retrieve", response_model=PolicyRetrievalResponse)
def retrieve(
    request: PolicyRetrievalRequest,
    identity: dict = Depends(require_policy_reader),
    db: Session = Depends(get_db),
):
    try:
        embedding = create_query_embedding(request.query)
    except EmbeddingServiceError as exc:
        logger.warning("Policy embedding unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "EMBEDDING_UNAVAILABLE", "message": "Embedding service is unavailable."},
        ) from exc

    result = retrieve_policy_evidence(
        db,
        identity["organization_id"],
        identity["role"],
        embedding,
        request.domain,
        request.document_type,
        request.policy_version,
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
