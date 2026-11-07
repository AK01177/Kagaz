"""
Unit and Integration Tests for DB-03: PostgreSQL Document and Extraction Persistence Integration.

Validates GitHub Issue #108 Acceptance Criteria:
1. Upload creates a database-backed document record.
2. Processing updates the database state (UPLOADED -> CLASSIFIED -> EXTRACTED / FAILED).
3. Extraction results remain available after backend restart (persisted across session/engine recreation).
4. Integrated APIs use database-backed records.
5. Extraction relationships: Document -> Extraction Run -> Extracted Fields.
6. JSON persistence removed from authoritative path / isolated as compatibility sidecar.
7. Safe migration of demo JSON records (idempotent, dry-run, malformed record handling).
8. Failure handling and rollback (no orphaned storage files on database failure).
9. Strict multi-tenant isolation across document and extraction retrieval.
"""
import io
import json
import time
from pathlib import Path
import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
import jwt

from app.db.base import Base
from app.db.session import get_db, get_engine
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction, ExtractionRun, ExtractionStatus
from app.schemas.extraction import (
    BaseDocumentExtraction,
    ExtractionCreate,
    InvoiceExtraction,
)
from app.crud.document import (
    create_document,
    create_document_metadata,
    delete_document,
    get_document_by_id,
    get_document_metadata,
    list_documents_by_organization,
    update_document_status,
)
from app.crud.extraction import (
    create_extraction,
    create_extraction_run,
    create_extractions_bulk,
    delete_extractions_by_document,
    get_document_extractions_summary,
    get_extractions_by_document,
    get_extraction_runs_by_document,
    get_latest_extraction_run,
)
from services.extraction_persistence import (
    ExtractionPersistenceError,
    persist_extraction_result,
    record_failed_extraction_run,
)
from services.upload import save_upload, UploadError
from storage.document_storage import DocumentStorage
from scripts.migrate_json_metadata import migrate_json_records
from main import app

JWT_SECRET = "db03-test-secret-at-least-32-bytes-long-12345"


def make_token(sub="test_user", org_id="org_alpha", role="SUBMITTER"):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "organization_id": org_id,
            "role": role,
            "active": True,
            "iss": "kagaz",
            "aud": "kagaz-api",
            "iat": now,
            "exp": now + 3600,
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def make_pdf(text: str = "Invoice #1001 for Kagaz Persistence Integration") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 750, text)
    c.save()
    return buf.getvalue()


@pytest.fixture
def sqlite_engine(tmp_path):
    """File-backed SQLite engine to verify persistence across session/engine recreation."""
    db_file = tmp_path / "test_db03.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db(sqlite_engine):
    Session = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def storage(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return DocumentStorage(base_dir=storage_dir)


@pytest.fixture
def client(monkeypatch, storage, db, sqlite_engine):
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(storage.base_dir))
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")

    # Wire get_db dependency
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.pop(get_db, None)


# ==============================================================================
# A. UPLOAD PERSISTENCE
# ==============================================================================

def test_upload_creates_database_backed_document_record(client, db, storage):
    """Verify that uploading a document creates an authoritative record in PostgreSQL."""
    pdf_bytes = make_pdf("Invoice #54321 Total: $120.00")
    token = make_token(sub="submitter_1", org_id="org_alpha", role="SUBMITTER")

    resp = client.post(
        "/api/documents",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    doc_id = data["document_id"]

    # Verify directly from database
    db_doc = db.query(Document).filter(Document.id == doc_id).first()
    assert db_doc is not None, "Document was not persisted to the database."
    assert db_doc.id == doc_id
    assert db_doc.organization_id == "org_alpha"
    assert db_doc.uploaded_by == "submitter_1"
    assert db_doc.filename == "invoice.pdf"
    assert db_doc.file_type == "application/pdf"
    assert db_doc.file_size == len(pdf_bytes)
    assert db_doc.upload_timestamp is not None
    assert db_doc.status in [DocumentStatus.UPLOADED, DocumentStatus.CLASSIFIED, DocumentStatus.EXTRACTED]
    assert Path(db_doc.storage_path).exists()


# ==============================================================================
# B. METADATA RETRIEVAL FROM DATABASE
# ==============================================================================

def test_metadata_retrieval_uses_database_record(client, db, storage):
    """Verify GET /api/documents/{id} retrieves authoritative metadata from PostgreSQL."""
    # Insert document directly into database without JSON metadata
    doc = Document(
        id="doc_direct_db_001",
        organization_id="org_alpha",
        uploaded_by="usr_alpha",
        filename="contract_direct.pdf",
        file_type="application/pdf",
        file_size=2048,
        storage_path=str(storage.base_dir / "doc_direct_db_001.pdf"),
        status=DocumentStatus.CLASSIFIED,
        classification="general_confidential",
        classification_confidence=0.94,
    )
    db.add(doc)
    db.commit()

    token = make_token(sub="usr_alpha", org_id="org_alpha", role="SUBMITTER")
    resp = client.get(
        f"/api/documents/{doc.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["document_id"] == "doc_direct_db_001"
    assert body["filename"] == "contract_direct.pdf"
    assert body["category"] == "general_confidential"
    assert body["confidence"] == pytest.approx(0.94)
    assert body["status"] == "CLASSIFIED"


# ==============================================================================
# C. PROCESSING STATUS TRANSITIONS
# ==============================================================================

def test_processing_updates_database_state(db):
    """Verify processing lifecycle updates PostgreSQL status and timestamps."""
    doc = create_document(
        db,
        organization_id="org_beta",
        uploaded_by="usr_beta",
        filename="receipt.pdf",
        file_type="application/pdf",
        file_size=500,
        storage_path="/storage/receipt.pdf",
        status=DocumentStatus.UPLOADED,
    )
    assert doc.status == DocumentStatus.UPLOADED
    assert doc.processed_at is None

    # Step 1: Classification
    doc.classification = "financial"
    doc.classification_confidence = 0.88
    doc.status = DocumentStatus.CLASSIFIED
    db.commit()
    db.refresh(doc)
    assert doc.status == DocumentStatus.CLASSIFIED
    assert doc.classification == "financial"

    # Step 2: Extraction
    doc.status = DocumentStatus.EXTRACTED
    db.commit()
    db.refresh(doc)
    assert doc.status == DocumentStatus.EXTRACTED


# ==============================================================================
# D. EXTRACTION RESULTS PERSISTENCE & AUDIT
# ==============================================================================

class _SampleExtraction(BaseDocumentExtraction):
    def to_flat_dict(self):
        return {
            "invoice_number": "INV-7788",
            "total_amount": "450.00",
            "supplier_name": "Antigravity Corp",
        }

    def get_field_confidences(self):
        return {
            "invoice_number": 0.99,
            "total_amount": 0.95,
            "supplier_name": 0.91,
        }


def test_extraction_results_persisted_in_database(db):
    """Verify structured fields and confidence values are persisted in extractions table."""
    doc = create_document(
        db,
        organization_id="org_gamma",
        uploaded_by="usr_gamma",
        filename="invoice.pdf",
        file_type="application/pdf",
        file_size=1200,
        storage_path="/storage/inv.pdf",
        status=DocumentStatus.CLASSIFIED,
        classification="financial",
    )

    records = persist_extraction_result(db, doc.id, _SampleExtraction())
    assert len(records) == 3

    # Check database rows
    saved_extractions = get_extractions_by_document(db, doc.id)
    assert len(saved_extractions) == 3
    extracted_map = {e.field_name: (e.value, e.confidence) for e in saved_extractions}
    assert extracted_map["invoice_number"] == ("INV-7788", pytest.approx(0.99))
    assert extracted_map["total_amount"] == ("450.00", pytest.approx(0.95))
    assert extracted_map["supplier_name"] == ("Antigravity Corp", pytest.approx(0.91))


# ==============================================================================
# E. EXTRACTION RELATIONSHIPS: Document -> Extraction Run -> Extracted Fields
# ==============================================================================

def test_extraction_hierarchical_relationships(db):
    """Verify Document -> Extraction Run -> Extracted Fields linking."""
    doc = create_document(
        db,
        organization_id="org_rel",
        uploaded_by="usr_rel",
        filename="invoice_rel.pdf",
        file_type="application/pdf",
        file_size=1000,
        storage_path="/storage/rel.pdf",
        status=DocumentStatus.CLASSIFIED,
        classification="financial",
    )

    # 1. Create discrete run
    run = create_extraction_run(
        db,
        document_id=doc.id,
        status=ExtractionStatus.SUCCESS,
        document_type="financial",
    )
    assert run.id is not None
    assert run.document_id == doc.id
    assert run.status == ExtractionStatus.SUCCESS

    # 2. Add extractions associated with run
    create_extractions_bulk(
        db,
        document_id=doc.id,
        extractions_data=[
            ExtractionCreate(field_name="invoice_id", value="INV-99", confidence=0.98),
            ExtractionCreate(field_name="total", value="99.99", confidence=0.92),
        ],
        extraction_run_id=run.id,
    )

    # 3. Query through relationships
    db.refresh(doc)
    assert len(doc.extraction_runs) == 1
    assert doc.extraction_runs[0].id == run.id

    assert len(run.extractions) == 2
    for ext in run.extractions:
        assert ext.document_id == doc.id
        assert ext.extraction_run_id == run.id
        assert ext.document == doc
        assert ext.extraction_run == run


def test_failed_extraction_run_does_not_corrupt_previous_results(db):
    """Verify that a failed extraction attempt records a failed run without wiping existing fields."""
    doc = create_document(
        db,
        organization_id="org_audit",
        uploaded_by="usr_audit",
        filename="test.pdf",
        file_type="application/pdf",
        file_size=800,
        storage_path="/storage/test.pdf",
    )

    # Successful run 1
    persist_extraction_result(db, doc.id, _SampleExtraction())
    initial_extractions = get_extractions_by_document(db, doc.id)
    assert len(initial_extractions) == 3

    # Attempt 2 fails
    failed_run = record_failed_extraction_run(
        db,
        document_id=doc.id,
        document_type="financial",
        error_message="OCR connection timeout",
    )
    assert failed_run.status == ExtractionStatus.FAILED
    assert failed_run.error_message == "OCR connection timeout"

    # Verify previous successful extraction fields are completely intact
    preserved_extractions = get_extractions_by_document(db, doc.id)
    assert len(preserved_extractions) == 3

    # Verify both runs are recorded in history
    runs = get_extraction_runs_by_document(db, doc.id)
    assert len(runs) == 2
    assert {r.status for r in runs} == {ExtractionStatus.SUCCESS, ExtractionStatus.FAILED}


# ==============================================================================
# F. RESTART PERSISTENCE ACROSS APPLICATION / SESSION RECREATION
# ==============================================================================

def test_persistence_survives_backend_restart(tmp_path):
    """Verify that document metadata and extraction results survive backend/session recreation."""
    db_file = tmp_path / "persistent_restart.db"
    db_url = f"sqlite:///{db_file}"

    # --- SESSION 1: Ingestion & Extraction ---
    engine1 = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine1)
    Session1 = sessionmaker(bind=engine1)
    s1 = Session1()

    doc = create_document(
        s1,
        id="doc_restart_test_101",
        organization_id="org_persist",
        uploaded_by="usr_persist",
        filename="audit_log.pdf",
        file_type="application/pdf",
        file_size=4096,
        storage_path="/storage/audit_log.pdf",
        status=DocumentStatus.EXTRACTED,
        classification="financial",
        classification_confidence=0.96,
    )
    persist_extraction_result(s1, doc.id, _SampleExtraction())
    s1.close()
    engine1.dispose()

    # --- SIMULATE BACKEND RESTART: Fresh engine & session factory ---
    engine2 = create_engine(db_url, connect_args={"check_same_thread": False})
    Session2 = sessionmaker(bind=engine2)
    s2 = Session2()

    # Verify document survived restart
    recovered_doc = s2.query(Document).filter(Document.id == "doc_restart_test_101").first()
    assert recovered_doc is not None
    assert recovered_doc.filename == "audit_log.pdf"
    assert recovered_doc.status == DocumentStatus.EXTRACTED
    assert recovered_doc.classification == "financial"
    assert recovered_doc.classification_confidence == pytest.approx(0.96)

    # Verify extractions survived restart
    recovered_extractions = s2.query(Extraction).filter(Extraction.document_id == "doc_restart_test_101").all()
    assert len(recovered_extractions) == 3
    field_map = {e.field_name: e.value for e in recovered_extractions}
    assert field_map["invoice_number"] == "INV-7788"
    assert field_map["supplier_name"] == "Antigravity Corp"

    # Verify extraction run survived restart
    recovered_run = s2.query(ExtractionRun).filter(ExtractionRun.document_id == "doc_restart_test_101").first()
    assert recovered_run is not None
    assert recovered_run.status == ExtractionStatus.SUCCESS

    s2.close()
    engine2.dispose()


# ==============================================================================
# G. FAILURE HANDLING & ROLLBACK
# ==============================================================================

def test_database_failure_rolls_back_storage_upload(storage, monkeypatch):
    """Verify that if database persistence fails, partial storage files are removed."""
    from unittest.mock import Mock

    mock_db = Mock()
    mock_db.add.side_effect = Exception("Simulated PostgreSQL connection failure")

    pdf_bytes = make_pdf("Failure rollback test")
    upload_file = Mock()
    upload_file.filename = "fail_test.pdf"
    upload_file.content_type = "application/pdf"
    upload_file.file = io.BytesIO(pdf_bytes)

    user = {"sub": "user_err", "organization_id": "org_err"}

    with pytest.raises(UploadError) as exc_info:
        save_upload(upload_file, storage, user, db=mock_db)

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "STORAGE_FAILURE"

    # Verify no orphaned document or metadata files remain in storage
    stored_files = list(storage.base_dir.glob("*.pdf"))
    assert len(stored_files) == 0, f"Found orphaned storage files: {stored_files}"


# ==============================================================================
# H. MULTI-TENANT ISOLATION
# ==============================================================================

def test_tenant_isolation_prevents_cross_org_access(client, db):
    """Verify users from one organization cannot view another organization's documents or extractions."""
    # Org A document
    doc_a = create_document(
        db,
        organization_id="org_tenant_A",
        uploaded_by="usr_A",
        filename="confidential_A.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="/storage/conf_A.pdf",
        status=DocumentStatus.EXTRACTED,
        classification="financial",
    )
    persist_extraction_result(db, doc_a.id, _SampleExtraction())

    # User B belonging to Org B
    token_b = make_token(sub="usr_B", org_id="org_tenant_B", role="REVIEWER")

    # Attempt to retrieve document metadata
    resp_meta = client.get(
        f"/api/documents/{doc_a.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_meta.status_code == 403, "Cross-tenant document metadata access was not denied!"

    # Attempt to retrieve extraction results
    resp_extract = client.get(
        f"/api/documents/{doc_a.id}/extract",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_extract.status_code == 403, "Cross-tenant extraction access was not denied!"


# ==============================================================================
# I. JSON COMPATIBILITY & MIGRATION UTILITY
# ==============================================================================

def test_json_demo_record_migration(db, storage):
    """Verify that existing demo JSON records can be migrated to PostgreSQL without data loss."""
    metadata_dir = storage.base_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create sample demo JSON record
    demo_doc_id = "doc_demo_legacy_001"
    pdf_path = storage.base_dir / f"{demo_doc_id}.pdf"
    pdf_path.write_bytes(make_pdf("Legacy demo document"))

    demo_json = {
        "document_id": demo_doc_id,
        "filename": "demo_invoice.pdf",
        "file_type": "application/pdf",
        "file_size": 1500,
        "storage_path": str(pdf_path),
        "status": "EXTRACTED",
        "uploaded_at": "2026-10-15T12:00:00Z",
        "category": "financial",
        "confidence": 0.95,
        "organization_id": "org_demo",
        "submitter_id": "usr_demo",
        "extracted_fields": {
            "invoice_number": "INV-DEMO-1",
            "total_amount": "999.00",
        },
        "extracted_confidence": {
            "invoice_number": 0.98,
            "total_amount": 0.95,
        },
    }
    (metadata_dir / f"{demo_doc_id}.json").write_text(json.dumps(demo_json))

    # Also add a malformed JSON to test resilience
    (metadata_dir / "malformed.json").write_text("NOT_JSON{")

    # 2. Test DRY-RUN mode first
    dry_result = migrate_json_records(db, storage.base_dir, dry_run=True)
    assert dry_result.scanned == 2
    assert dry_result.migrated == 1
    assert dry_result.failed == 1
    # Verify no records inserted in DB during dry-run
    assert db.query(Document).filter(Document.id == demo_doc_id).first() is None

    # 3. Test LIVE migration
    live_result = migrate_json_records(db, storage.base_dir, dry_run=False)
    assert live_result.migrated == 1
    assert live_result.failed == 1

    # Verify record in database
    migrated_doc = db.query(Document).filter(Document.id == demo_doc_id).first()
    assert migrated_doc is not None
    assert migrated_doc.filename == "demo_invoice.pdf"
    assert migrated_doc.status == DocumentStatus.EXTRACTED
    assert migrated_doc.organization_id == "org_demo"

    migrated_fields = get_extractions_by_document(db, demo_doc_id)
    assert len(migrated_fields) == 2
    field_dict = {f.field_name: f.value for f in migrated_fields}
    assert field_dict["invoice_number"] == "INV-DEMO-1"
    assert field_dict["total_amount"] == "999.00"

    # 4. Test IDEMPOTENCY: running migration again skips already imported records
    idempotent_result = migrate_json_records(db, storage.base_dir, dry_run=False)
    assert idempotent_result.skipped == 1
    assert idempotent_result.migrated == 0

    # Original files must remain intact
    assert (metadata_dir / f"{demo_doc_id}.json").exists()
    assert pdf_path.exists()


# ==============================================================================
# J. INTEGRATED APIS: LISTING & DELETION
# ==============================================================================

def test_document_listing_and_deletion_endpoints(client, db, storage):
    """Verify GET /api/documents and DELETE /api/documents/{id} backed by PostgreSQL."""
    token = make_token(sub="usr_admin", org_id="org_crud", role="SUBMITTER")

    # Create two documents
    doc1 = create_document(
        db,
        id="doc_crud_1",
        organization_id="org_crud",
        uploaded_by="usr_admin",
        filename="file1.pdf",
        file_type="application/pdf",
        file_size=100,
        storage_path=str(storage.base_dir / "doc_crud_1.pdf"),
    )
    doc2 = create_document(
        db,
        id="doc_crud_2",
        organization_id="org_crud",
        uploaded_by="usr_admin",
        filename="file2.pdf",
        file_type="application/pdf",
        file_size=200,
        storage_path=str(storage.base_dir / "doc_crud_2.pdf"),
    )
    (storage.base_dir / "doc_crud_1.pdf").write_bytes(b"%PDF-test1")
    (storage.base_dir / "doc_crud_2.pdf").write_bytes(b"%PDF-test2")

    # 1. List documents
    resp_list = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert len(items) == 2
    doc_ids = {item["document_id"] for item in items}
    assert doc_ids == {"doc_crud_1", "doc_crud_2"}

    # 2. Delete document
    resp_del = client.delete("/api/documents/doc_crud_1", headers={"Authorization": f"Bearer {token}"})
    assert resp_del.status_code == 200

    # Verify deleted from DB
    assert db.query(Document).filter(Document.id == "doc_crud_1").first() is None
    # Verify file deleted from storage
    assert not (storage.base_dir / "doc_crud_1.pdf").exists()

    # Remaining document intact
    assert db.query(Document).filter(Document.id == "doc_crud_2").first() is not None
    assert (storage.base_dir / "doc_crud_2.pdf").exists()



# ==============================================================================
# K. JSON FALLBACK ISOLATION TESTS (Issue #5 of the prompt)
# ==============================================================================

def test_postgresql_takes_precedence_over_json_sidecar(client, db, storage, monkeypatch):
    """Acceptance criterion: APIs use database-backed records.

    When KAGAZ_LEGACY_JSON_FALLBACK=1, a JSON sidecar with stale data must NOT
    override the authoritative PostgreSQL record.  The API must return the value
    from PostgreSQL even when the JSON sidecar says something different.
    """
    monkeypatch.setenv("KAGAZ_LEGACY_JSON_FALLBACK", "1")
    token = make_token(sub="usr_p", org_id="org_precedence", role="SUBMITTER")

    # Create the document record in PostgreSQL with known values
    doc = create_document(
        db,
        id="doc_precedence_001",
        organization_id="org_precedence",
        uploaded_by="usr_p",
        filename="real.pdf",
        file_type="application/pdf",
        file_size=1234,
        storage_path=str(storage.base_dir / "doc_precedence_001.pdf"),
        status=DocumentStatus.CLASSIFIED,
        classification="financial",
        classification_confidence=0.9,
    )

    # Write a JSON sidecar with intentionally stale / different values
    metadata_dir = storage.base_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    stale_json = {
        "document_id": "doc_precedence_001",
        "filename": "stale.pdf",          # <-- intentionally wrong
        "file_type": "application/pdf",
        "file_size": 9999,                 # <-- intentionally wrong
        "status": "UPLOADED",             # <-- stale (DB says CLASSIFIED)
        "category": "hr_documents",       # <-- stale (DB says financial)
        "confidence": 0.1,
        "uploaded_at": "2020-01-01T00:00:00Z",
        "submitter_id": "usr_p",
        "organization_id": "org_precedence",
    }
    (metadata_dir / "doc_precedence_001.json").write_text(json.dumps(stale_json))

    # API must return authoritative PostgreSQL data, not the stale JSON sidecar
    resp = client.get(
        "/api/documents/doc_precedence_001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "real.pdf", "API returned stale filename from JSON sidecar"
    assert body["file_size"] == 1234, "API returned stale file_size from JSON sidecar"
    assert body["status"] == "CLASSIFIED", "API returned stale status from JSON sidecar"
    assert body["category"] == "financial", "API returned stale category from JSON sidecar"


def test_production_mode_disables_json_fallback(client, db, storage, monkeypatch):
    """Acceptance criterion: JSON is not authoritative in production.

    When KAGAZ_LEGACY_JSON_FALLBACK is NOT set (production default),
    a document that only exists in a JSON sidecar must return 404,
    not silently serve the stale JSON record.
    """
    # Explicitly clear the flag to simulate production mode
    monkeypatch.delenv("KAGAZ_LEGACY_JSON_FALLBACK", raising=False)
    token = make_token(sub="usr_prod", org_id="org_prod", role="SUBMITTER")

    # Write a JSON sidecar — but do NOT create a PostgreSQL record
    metadata_dir = storage.base_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    legacy_json = {
        "document_id": "doc_json_only_legacy",
        "filename": "legacy.pdf",
        "file_type": "application/pdf",
        "file_size": 500,
        "status": "UPLOADED",
        "uploaded_at": "2020-01-01T00:00:00Z",
        "submitter_id": "usr_prod",
        "organization_id": "org_prod",
    }
    (metadata_dir / "doc_json_only_legacy.json").write_text(json.dumps(legacy_json))

    # In production mode: 404, not the stale JSON response
    resp = client.get(
        "/api/documents/doc_json_only_legacy",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, (
        "Production mode must not fall back to JSON sidecar — expected 404, "
        f"got {resp.status_code}: {resp.text}"
    )


def test_legacy_fallback_enabled_serves_json_sidecar(client, db, storage, monkeypatch):
    """When KAGAZ_LEGACY_JSON_FALLBACK=1, unmigrated demo records are served from JSON.

    This is the ONLY production-disabled scenario where JSON is authoritative:
    a document that exists only in the JSON sidecar can be fetched when the
    fallback flag is explicitly enabled.
    """
    monkeypatch.setenv("KAGAZ_LEGACY_JSON_FALLBACK", "1")
    token = make_token(sub="usr_fallback", org_id="org_fb", role="SUBMITTER")

    # Write a JSON sidecar — do NOT create a PostgreSQL record
    metadata_dir = storage.base_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    legacy_json = {
        "document_id": "doc_legacy_fb_001",
        "filename": "legacy_demo.pdf",
        "file_type": "application/pdf",
        "file_size": 750,
        "status": "UPLOADED",
        "uploaded_at": "2021-06-01T10:00:00Z",
        "submitter_id": "usr_fallback",
        "organization_id": "org_fb",
    }
    (metadata_dir / "doc_legacy_fb_001.json").write_text(json.dumps(legacy_json))

    # With KAGAZ_LEGACY_JSON_FALLBACK=1, the sidecar should be served
    resp = client.get(
        "/api/documents/doc_legacy_fb_001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "legacy_demo.pdf"
    assert body["organization_id"] == "org_fb"


def test_extraction_fallback_disabled_in_production(client, db, storage, monkeypatch):
    """DB-03: GET /api/documents/{id}/extract must NOT fall back to JSON in production.

    When a document exists in PostgreSQL but has no extraction records yet,
    the endpoint returns empty fields (not stale JSON extractions).
    """
    monkeypatch.delenv("KAGAZ_LEGACY_JSON_FALLBACK", raising=False)
    token = make_token(sub="usr_extr", org_id="org_extr", role="REVIEWER")

    # Create document in DB (no extractions)
    doc = create_document(
        db,
        id="doc_no_extract_001",
        organization_id="org_extr",
        uploaded_by="usr_extr",
        filename="pending.pdf",
        file_type="application/pdf",
        file_size=800,
        storage_path=str(storage.base_dir / "doc_no_extract_001.pdf"),
        status=DocumentStatus.CLASSIFIED,
        classification="financial",
    )

    # Write JSON sidecar with stale extracted fields
    metadata_dir = storage.base_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    stale = {
        "document_id": "doc_no_extract_001",
        "extracted_fields": {"invoice_number": "STALE-001"},
        "extracted_confidence": {"invoice_number": 0.99},
        "status": "EXTRACTED",
        "category": "financial",
        "organization_id": "org_extr",
    }
    (metadata_dir / "doc_no_extract_001.json").write_text(json.dumps(stale))

    resp = client.get(
        "/api/documents/doc_no_extract_001/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # PostgreSQL has no extractions — must NOT show stale JSON extraction
    assert body["fields"] == {}, (
        "API served stale JSON extractions instead of authoritative empty DB response"
    )
    assert "invoice_number" not in body["fields"]


def test_upload_does_not_write_json_sidecar_in_production(
    client, db, storage, tmp_path, monkeypatch
):
    """DB-03: Upload must not write a JSON sidecar when KAGAZ_LEGACY_JSON_FALLBACK is unset.

    In production, PostgreSQL is the sole store; no JSON sidecar is created.
    """
    monkeypatch.delenv("KAGAZ_LEGACY_JSON_FALLBACK", raising=False)
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(storage.base_dir))
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")

    token = make_token(sub="usr_nojson", org_id="org_nojson", role="SUBMITTER")
    pdf_bytes = make_pdf("Invoice #9999 — no sidecar in production")

    resp = client.post(
        "/api/documents",
        files={"file": ("nojson.pdf", pdf_bytes, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["document_id"]

    # No JSON sidecar should have been written
    metadata_dir = storage.base_dir / "metadata"
    sidecar = metadata_dir / f"{doc_id}.json"
    assert not sidecar.exists(), (
        f"JSON sidecar was written in production mode (KAGAZ_LEGACY_JSON_FALLBACK not set): {sidecar}"
    )

    # PostgreSQL record must exist
    pg_doc = db.query(Document).filter(Document.id == doc_id).first()
    assert pg_doc is not None, "Document was not persisted to PostgreSQL"
    assert pg_doc.organization_id == "org_nojson"
