"""
Tests for DB-03: PostgreSQL Document and Extraction Persistence Integration.

Verifies that:
- Uploading a document persists the Document record to the database.
- Extracted structured fields are persisted to the extractions table.
- Ingestion, retrieval, and status updates maintain database consistency.
- Multi-tenant organization isolation is enforced in DB queries.
- Cascade delete removes extraction child records when a document is deleted.
"""
import io
import pathlib
import tempfile
import uuid
import pytest
from reportlab.pdfgen import canvas
from fastapi import UploadFile
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.schemas.document import DocumentMetadataCreate, DocumentStatusUpdate
from app.schemas.extraction import ExtractionCreate
from app.crud.document import (
    create_document_metadata,
    get_document_metadata,
    update_document_status,
)
from app.crud.extraction import (
    create_extractions_bulk,
    get_document_extractions_summary,
    get_extractions_by_document,
)
from services.upload import save_upload
from storage.document_storage import DocumentStorage


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database enforcing foreign keys."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_pdf():
    stream = io.BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(72, 800, "Invoice Number: INV-2026-001\nTotal: $1,250.00\nSupplier: Acme Corp")
    c.save()
    return stream.getvalue()


class TestDB03DocumentPersistence:
    """Document metadata database persistence tests."""

    def test_create_and_fetch_document_in_db(self, db_session):
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        doc_id = f"doc_{uuid.uuid4().hex}"

        doc_data = DocumentMetadataCreate(
            id=doc_id,
            organization_id=org_id,
            uploaded_by=user_id,
            filename="receipt.pdf",
            file_type="application/pdf",
            file_size=2048,
            storage_path="storage_data/receipt.pdf",
            status=DocumentStatus.CLASSIFIED,
            classification="financial",
            classification_confidence=0.96,
        )

        created = create_document_metadata(db_session, doc_data, document_id=doc_id)
        assert created.id == doc_id
        assert created.filename == "receipt.pdf"
        assert created.classification == "financial"
        assert created.classification_confidence == 0.96

        # Fetch from DB
        fetched = get_document_metadata(db_session, doc_id, str(org_id))
        assert fetched is not None
        assert fetched.id == doc_id
        assert fetched.organization_id == str(org_id)
        assert fetched.uploaded_by == str(user_id)

    def test_tenant_isolation_in_db_query(self, db_session):
        org_a = uuid.uuid4()
        org_b = uuid.uuid4()
        doc_id = f"doc_{uuid.uuid4().hex}"

        create_document_metadata(
            db_session,
            DocumentMetadataCreate(
                id=doc_id,
                organization_id=org_a,
                uploaded_by=uuid.uuid4(),
                filename="secret.pdf",
                file_type="application/pdf",
                file_size=1024,
                storage_path="storage_data/secret.pdf",
            ),
            document_id=doc_id,
        )

        # Org A can see it
        assert get_document_metadata(db_session, doc_id, str(org_a)) is not None
        # Org B cannot see it
        assert get_document_metadata(db_session, doc_id, str(org_b)) is None

    def test_update_document_classification_in_db(self, db_session):
        org_id = uuid.uuid4()
        doc_id = f"doc_{uuid.uuid4().hex}"

        create_document_metadata(
            db_session,
            DocumentMetadataCreate(
                id=doc_id,
                organization_id=org_id,
                uploaded_by=uuid.uuid4(),
                filename="document.pdf",
                file_type="application/pdf",
                file_size=1024,
                storage_path="storage_data/document.pdf",
                status=DocumentStatus.UPLOADED,
            ),
            document_id=doc_id,
        )

        update_data = DocumentStatusUpdate(
            status=DocumentStatus.CLASSIFIED,
            classification="hr",
            classification_confidence=0.99,
        )
        updated = update_document_status(db_session, doc_id, str(org_id), update_data)
        assert updated is not None
        assert updated.status == DocumentStatus.CLASSIFIED
        assert updated.classification == "hr"
        assert updated.classification_confidence == 0.99


class TestDB03ExtractionPersistence:
    """Extraction child table integration tests."""

    def test_persist_extractions_linked_to_document(self, db_session):
        doc_id = f"doc_{uuid.uuid4().hex}"
        create_document_metadata(
            db_session,
            DocumentMetadataCreate(
                id=doc_id,
                organization_id=uuid.uuid4(),
                uploaded_by=uuid.uuid4(),
                filename="invoice.pdf",
                file_type="application/pdf",
                file_size=1024,
                storage_path="storage_data/invoice.pdf",
                status=DocumentStatus.CLASSIFIED,
                classification="financial",
            ),
            document_id=doc_id,
        )

        fields = [
            ExtractionCreate(field_name="invoice_number", value="INV-100", confidence=0.95),
            ExtractionCreate(field_name="total_amount", value="1500.00", confidence=0.90),
            ExtractionCreate(field_name="vendor", value="Tech Corp", confidence=0.85),
        ]
        create_extractions_bulk(db_session, doc_id, fields)

        stored = get_extractions_by_document(db_session, doc_id)
        assert len(stored) == 3
        assert {e.field_name for e in stored} == {"invoice_number", "total_amount", "vendor"}

        summary = get_document_extractions_summary(db_session, doc_id)
        assert summary is not None
        assert summary.fields["invoice_number"] == "INV-100"
        assert summary.fields["total_amount"] == "1500.00"
        assert summary.confidence["vendor"] == pytest.approx(0.85)

    def test_cascade_delete_removes_extractions(self, db_session):
        doc_id = f"doc_{uuid.uuid4().hex}"
        doc = create_document_metadata(
            db_session,
            DocumentMetadataCreate(
                id=doc_id,
                organization_id=uuid.uuid4(),
                uploaded_by=uuid.uuid4(),
                filename="invoice.pdf",
                file_type="application/pdf",
                file_size=1024,
                storage_path="storage_data/invoice.pdf",
            ),
            document_id=doc_id,
        )

        create_extractions_bulk(db_session, doc_id, [
            ExtractionCreate(field_name="f1", value="v1", confidence=0.9),
            ExtractionCreate(field_name="f2", value="v2", confidence=0.8),
        ])

        assert len(get_extractions_by_document(db_session, doc_id)) == 2

        # Delete parent document
        db_session.delete(doc)
        db_session.commit()

        # Child extractions must be cascaded
        assert len(get_extractions_by_document(db_session, doc_id)) == 0


class TestDB03SaveUploadIntegration:
    """Full save_upload pipeline database persistence tests."""

    def test_save_upload_persists_to_db(self, db_session, sample_pdf, monkeypatch):
        from services.classification import ClassificationResult, DocumentCategory
        monkeypatch.setattr(
            "services.upload.classify_document",
            lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.95),
        )

        with tempfile.TemporaryDirectory() as td:
            storage = DocumentStorage(base_dir=pathlib.Path(td))
            upload_file = UploadFile(filename="invoice.pdf", file=io.BytesIO(sample_pdf))
            user = {
                "sub": str(uuid.uuid4()),
                "organization_id": str(uuid.uuid4()),
            }

            res = save_upload(upload_file, storage, user, db=db_session)
            assert res["status"] in ("CLASSIFIED", "EXTRACTED")
            doc_id = res["document_id"]

            # Check DB record
            doc_in_db = db_session.query(Document).filter(Document.id == doc_id).first()
            assert doc_in_db is not None
            assert doc_in_db.filename == "invoice.pdf"
            assert doc_in_db.file_type == "application/pdf"
            assert doc_in_db.organization_id == user["organization_id"]
            assert doc_in_db.uploaded_by == user["sub"]
            assert doc_in_db.classification == "financial"
            assert doc_in_db.classification_confidence == 0.95
