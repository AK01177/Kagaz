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
from services.document_types import require_document_type
from services.policy_ingestion import index_text_policy_version, ingest_policy_version
from services.policy_retrieval import (
    EmbeddingServiceError,
    create_query_embedding,
    retrieve_policy_evidence,
)
from services.policy_text import (
    SUPPORTED_POLICY_EXTENSIONS,
    SUPPORTED_POLICY_FORMATS,
    PolicyFileError,
    validate_policy_file,
)
from services.upload import CHUNK_BYTES, MAX_UPLOAD_BYTES
from storage.s3_policy_storage import S3PolicyStorage, get_policy_storage


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/policies",
    tags=["policies"],
    route_class=UploadLimitRoute,
)


def _ingestion_response(
    policy: Policy,
    version: PolicyVersion,
    source: Document | None,
    chunk_count: int,
) -> PolicyIngestionResponse:
    return PolicyIngestionResponse(
        policy_id=policy.id,
        policy_version_id=version.id,
        source_document_id=source.id if source else None,
        source_filename=source.filename if source else None,
        version=version.version,
        status=version.status.value,
        chunk_count=chunk_count,
        ingestion_error=version.ingestion_error,
    )


def _discard_source(storage, document_id: str, extension: str, local_path) -> None:
    """Remove a source file that was stored but never recorded."""
    if isinstance(storage, S3PolicyStorage):
        storage.delete(document_id, extension)
    elif local_path is not None:
        local_path.unlink(missing_ok=True)


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
    domain = domain.strip().lower() if domain and domain.strip() else None
    try:
        document_type = require_document_type(document_type)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "UNKNOWN_DOCUMENT_TYPE", "message": str(exc)}) from exc
    if not policy_name or not version_name:
        raise HTTPException(422, detail={
            "code": "INVALID_POLICY_METADATA",
            "message": "Policy name and version must contain text.",
        })

    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    extension = Path(filename).suffix.lower()
    if not filename or "\x00" in filename or extension not in SUPPORTED_POLICY_FORMATS:
        raise HTTPException(415, detail={
            "code": "UNSUPPORTED_POLICY_FORMAT",
            "message": f"Policy files must be one of: {SUPPORTED_POLICY_EXTENSIONS}.",
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
    storage = get_policy_storage()
    use_s3 = isinstance(storage, S3PolicyStorage)
    if not use_s3:
        storage.base_dir.mkdir(parents=True, exist_ok=True)
    document_id = f"doc_{uuid4().hex}"
    document_path = None if use_s3 else storage.base_dir / f"{document_id}{extension}"
    storage_path = None
    size = 0
    try:
        # Validate in a staging directory so rejected uploads never leave a partial source file.
        with TemporaryDirectory(
            prefix="policy_upload_", dir=None if use_s3 else storage.base_dir
        ) as staging:
            staged_path = Path(staging) / f"policy{extension}"
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
                    "message": "The uploaded file is empty.",
                })
            try:
                validate_policy_file(staged_path, extension)
            except PolicyFileError as exc:
                raise HTTPException(400, detail={
                    "code": "INVALID_FILE",
                    "message": str(exc),
                }) from exc
            if use_s3:
                storage_path = storage.store(staged_path, document_id, extension)
            else:
                staged_path.replace(document_path)
                storage_path = str(document_path.resolve())

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
            file_type=SUPPORTED_POLICY_FORMATS[extension],
            file_size=size,
            storage_path=storage_path,
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
        _discard_source(storage, document_id, extension, document_path)
        raise
    except Exception:
        db.rollback()
        _discard_source(storage, document_id, extension, document_path)
        logger.error("Could not record policy ingestion request")
        raise HTTPException(500, detail={
            "code": "POLICY_INGESTION_RECORD_FAILED",
            "message": "The policy ingestion request could not be recorded.",
        })

    chunk_count = ingest_policy_version(
        db,
        policy,
        version,
        filename,
        storage,
        expected_organization_id=identity["organization_id"],
    )
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
    """Submit a policy file (PDF, DOCX or TXT) for extraction, chunking and vector indexing."""
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
        .outerjoin(Document, Document.id == PolicyVersion.source_document_id)
        .filter(PolicyVersion.policy_id == policy.id)
        .order_by(PolicyVersion.created_at.desc())
        .all()
    )
    return [
        PolicyVersionSummary(
            created_at=version.created_at,
            policy_version_id=version.id,
            source_document_id=source.id if source else None,
            source_filename=source.filename if source else None,
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
    is_text_version = version.source_document_id is None
    source = None
    if not is_text_version:
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
    if is_text_version:
        chunk_count = await run_in_threadpool(index_text_policy_version, db, policy, version)
        db.refresh(version)
        return _ingestion_response(policy, version, None, chunk_count)
    storage = get_policy_storage()
    chunk_count = await run_in_threadpool(
        ingest_policy_version,
        db,
        policy,
        version,
        source.filename,
        storage,
        expected_organization_id=identity["organization_id"],
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
        query_text=request.query,
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
                source_filename=document.filename if document else None,
            )
            for policy, version, chunk, score, document in result.rows
        ],
    )
