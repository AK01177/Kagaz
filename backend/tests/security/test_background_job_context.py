"""Background job and worker organization-context enforcement tests (QA-08 Scope 9 & Section 10).

Verifies that background workers and processing services enforce organization boundaries,
prevent cross-tenant data leaks, fail closed on context mismatch, and correctly tag results.
"""
from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.policy import Policy, PolicyVersion, PolicyVersionStatus
from app.schemas.extraction import ExtractedField, InvoiceExtraction
from services.extraction_persistence import (
    ExtractionPersistenceError,
    persist_extraction_result,
)
from services.policy_ingestion import ingest_policy_version
from services.policy_validation import run_policy_validation
from services.upload import UploadError, save_upload
from services.validation import validate_document
from storage.document_storage import DocumentStorage
from tests.security.conftest import SecurityWorld, make_valid_pdf_bytes


def test_policy_ingestion_rejects_mismatched_organization_context(
    security_world: SecurityWorld, db_session: Session
) -> None:
    """Policy ingestion fails with status FAILED when expected_organization_id does not match policy."""
    storage = DocumentStorage()
    doc_file = security_world.storage_dir / "policy_doc.pdf"
    doc_file.write_bytes(make_valid_pdf_bytes("Policy Content"))

    src_doc = Document(
        id="doc_src_alpha",
        organization_id=security_world.org_alpha.id,
        uploaded_by=security_world.admin_a.id,
        filename="policy_doc.pdf",
        file_type="application/pdf",
        file_size=len(doc_file.read_bytes()),
        storage_path=str(doc_file.resolve()),
        status=DocumentStatus.EXTRACTED,
        classification="financial",
    )
    db_session.add(src_doc)
    db_session.flush()

    ver = PolicyVersion(
        id="ver_alpha_1",
        policy_id=security_world.policy_a.id,
        source_document_id=src_doc.id,
        version="v1.0",
        status=PolicyVersionStatus.PROCESSING,
    )
    db_session.add(ver)
    db_session.commit()

    # Pass expected_organization_id=org_beta (mismatch)
    chunks_created = ingest_policy_version(
        db_session,
        security_world.policy_a,
        ver,
        "policy_doc.pdf",
        storage,
        expected_organization_id=security_world.org_beta.id,
    )
    assert chunks_created == 0
    db_session.refresh(ver)
    assert ver.status == PolicyVersionStatus.FAILED
    assert "organization context mismatch" in (ver.ingestion_error or "").lower()


def test_policy_ingestion_rejects_cross_org_source_document(
    security_world: SecurityWorld, db_session: Session
) -> None:
    """Policy ingestion fails when source document belongs to a different organization."""
    storage = DocumentStorage()
    doc_file = security_world.storage_dir / "beta_source.pdf"
    doc_file.write_bytes(make_valid_pdf_bytes("Beta Source Document"))

    # Source document belongs to Org Beta
    cross_src = Document(
        id="doc_src_beta",
        organization_id=security_world.org_beta.id,
        uploaded_by=security_world.admin_b.id,
        filename="beta_source.pdf",
        file_type="application/pdf",
        file_size=len(doc_file.read_bytes()),
        storage_path=str(doc_file.resolve()),
        status=DocumentStatus.EXTRACTED,
        classification="financial",
    )
    db_session.add(cross_src)
    db_session.flush()

    # Version attached to Policy A (Org Alpha)
    ver = PolicyVersion(
        id="ver_alpha_cross",
        policy_id=security_world.policy_a.id,
        source_document_id=cross_src.id,
        version="v2.0",
        status=PolicyVersionStatus.PROCESSING,
    )
    db_session.add(ver)
    db_session.commit()

    chunks_created = ingest_policy_version(
        db_session,
        security_world.policy_a,
        ver,
        "beta_source.pdf",
        storage,
        expected_organization_id=security_world.org_alpha.id,
    )
    assert chunks_created == 0
    db_session.refresh(ver)
    assert ver.status == PolicyVersionStatus.FAILED
    assert "source document" in (ver.ingestion_error or "").lower()


def test_validation_background_service_enforces_organization_context(
    security_world: SecurityWorld, db_session: Session
) -> None:
    """Document validation service raises PermissionError when document or policy org mismatches."""
    # 1. Calling validate_document with mismatched organization_id
    with pytest.raises(PermissionError, match="different organization"):
        validate_document(
            document_id=security_world.doc_b.id,
            organization_id=security_world.org_alpha.id,  # Org A caller targeting Doc B
            domain="financial",
            extracted_fields={"invoice_number": "INV-1"},
            db=db_session,
        )

    # 2. Calling validate_document with mismatched policy
    with pytest.raises(PermissionError, match="different organization"):
        validate_document(
            document_id="unpersisted_doc",
            organization_id=security_world.org_alpha.id,
            domain="financial",
            policy=security_world.policy_b,  # Policy belongs to Org B
            extracted_fields={"invoice_number": "INV-1"},
        )


def test_policy_validation_runner_enforces_organization_context(
    security_world: SecurityWorld, db_session: Session
) -> None:
    """Policy validation runner raises 403 when document organization does not match identity."""
    identity_a = {
        "sub": security_world.reviewer_a.id,
        "organization_id": security_world.org_alpha.id,
        "role": "REVIEWER",
    }
    with pytest.raises(HTTPException) as exc_info:
        run_policy_validation(
            db_session,
            security_world.doc_b,  # Doc belongs to Org Beta
            identity_a,
        )
    assert exc_info.value.status_code == 403


def test_extraction_persistence_enforces_organization_context(
    security_world: SecurityWorld, db_session: Session
) -> None:
    """Persisting extraction results raises ExtractionPersistenceError if organization_id mismatches."""
    extraction = InvoiceExtraction(
        invoice_number=ExtractedField(value="INV-FAIL", confidence=0.9),
    )
    with pytest.raises(ExtractionPersistenceError):
        persist_extraction_result(
            db_session,
            security_world.doc_b.id,  # Doc belongs to Org Beta
            extraction,
            organization_id=security_world.org_alpha.id,  # Mismatched Org Alpha
        )


def test_upload_service_rejects_missing_organization_context(
    security_world: SecurityWorld, db_session: Session
) -> None:
    """Uploading without authenticated organization context raises UploadError(403)."""
    fake_upload = UploadFile(
        filename="test.pdf",
        file=BytesIO(make_valid_pdf_bytes("Upload test")),
    )
    with pytest.raises(UploadError) as exc_info:
        save_upload(
            fake_upload,
            DocumentStorage(),
            user={"sub": "usr_no_org", "organization_id": None},
            db=db_session,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "MEMBERSHIP_REQUIRED"
