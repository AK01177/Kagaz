import pytest
from reportlab.pdfgen import canvas

from services.extraction import extract_text, UnsupportedDocumentTypeError, ExtractionError
from storage.document_storage import DocumentStorage, DocumentNotFoundError


def _write_pdf(path, pages_lines):
    c = canvas.Canvas(str(path))
    for lines in pages_lines:
        y = 800
        for line in lines:
            c.drawString(72, y, line)
            y -= 20
        c.showPage()
    c.save()


@pytest.fixture
def storage(tmp_path):
    return DocumentStorage(base_dir=tmp_path)


def test_extracts_non_empty_text_for_readable_document(tmp_path, storage):
    _write_pdf(tmp_path / "doc_001.pdf", [["Hello world"]])

    text = extract_text("doc_001", storage=storage)

    assert text
    assert "Hello world" in text


def test_combines_text_from_multiple_pages_in_order(tmp_path, storage):
    _write_pdf(tmp_path / "doc_002.pdf", [["First page content"], ["Second page content"]])

    text = extract_text("doc_002", storage=storage)

    assert text.index("First page content") < text.index("Second page content")


def test_normalizes_obvious_whitespace(tmp_path, storage):
    _write_pdf(tmp_path / "doc_003.pdf", [["Spaced   out   text"]])

    text = extract_text("doc_003", storage=storage)

    assert "   " not in text
    assert text == text.strip()


def test_missing_document_raises_controlled_error(storage):
    with pytest.raises(DocumentNotFoundError):
        extract_text("does_not_exist", storage=storage)


def test_unsupported_file_type_raises_controlled_error(tmp_path, storage):
    (tmp_path / "doc_004.txt").write_text("plain text file")

    with pytest.raises(UnsupportedDocumentTypeError):
        extract_text("doc_004", storage=storage)


def test_unreadable_document_raises_controlled_error(tmp_path, storage):
    (tmp_path / "doc_005.pdf").write_bytes(b"not a real pdf")

    with pytest.raises(ExtractionError):
        extract_text("doc_005", storage=storage)


# Database persistence tests for DB-01

import time
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.document import Document
from app.models.extraction import Extraction
from app.schemas.extraction import ExtractionCreate
from app.crud.extraction import (
    create_extraction,
    create_extractions_bulk,
    get_extractions_by_document,
    get_document_extractions_summary,
    delete_extractions_by_document,
)


@pytest.fixture
def extraction_db():
    engine = create_engine("sqlite:///:memory:")

    # Explicitly enforce foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_save_and_retrieve_extraction(extraction_db):
    document = Document(
        organization_id="org-123",
        uploaded_by="user-123",
        filename="invoice.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="uploads/invoice.pdf",
    )
    extraction_db.add(document)
    extraction_db.commit()

    record = Extraction(
        document_id=document.id,
        field_name="invoice_number",
        value="INV-1001",
        confidence=0.98,
    )
    extraction_db.add(record)
    extraction_db.commit()

    saved = extraction_db.query(Extraction).filter_by(
        document_id=document.id
    ).first()

    assert saved is not None
    assert saved.field_name == "invoice_number"
    assert saved.value == "INV-1001"
    assert saved.confidence == pytest.approx(0.98)
    assert saved.created_at is not None
    assert saved.updated_at is not None


def test_extraction_rejects_invalid_confidence(extraction_db):
    document = Document(
        organization_id="org-123",
        uploaded_by="user-123",
        filename="invoice.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="uploads/invoice.pdf",
    )
    extraction_db.add(document)
    extraction_db.commit()

    record = Extraction(
        document_id=document.id,
        field_name="invoice_number",
        value="INV-1001",
        confidence=1.5,
    )
    extraction_db.add(record)

    with pytest.raises(IntegrityError):
        extraction_db.commit()

    extraction_db.rollback()


def test_extraction_foreign_key_enforcement(extraction_db):
    """Extraction must reference a valid document_id; orphaned extractions must fail."""
    record = Extraction(
        document_id="non-existent-doc-id",
        field_name="total_amount",
        value="5000",
        confidence=0.95,
    )
    extraction_db.add(record)

    with pytest.raises(IntegrityError):
        extraction_db.commit()

    extraction_db.rollback()


def test_extraction_relationship_and_cascade_delete(extraction_db):
    """Test bi-directional relationship and cascade deletion of extractions with document."""
    document = Document(
        organization_id="org-123",
        uploaded_by="user-123",
        filename="receipt.pdf",
        file_type="application/pdf",
        file_size=2048,
        storage_path="uploads/receipt.pdf",
    )
    extraction_db.add(document)
    extraction_db.commit()

    ext1 = Extraction(
        document_id=document.id,
        field_name="vendor",
        value="Acme Corp",
        confidence=0.95,
    )
    ext2 = Extraction(
        document_id=document.id,
        field_name="amount",
        value="250.00",
        confidence=0.90,
    )
    extraction_db.add_all([ext1, ext2])
    extraction_db.commit()

    # Relationship verification
    extraction_db.refresh(document)
    assert len(document.extractions) == 2
    assert ext1.document == document
    assert ext2.document == document

    # Cascade deletion verification
    extraction_db.delete(document)
    extraction_db.commit()

    remaining_exts = extraction_db.query(Extraction).filter_by(document_id=document.id).all()
    assert len(remaining_exts) == 0


def test_multiple_extracted_fields_persistence(extraction_db):
    """Verify that multiple fields for one document are persisted as separate records."""
    document = Document(
        organization_id="org-finance",
        uploaded_by="user-456",
        filename="invoice_multi.pdf",
        file_type="application/pdf",
        file_size=4096,
        storage_path="uploads/invoice_multi.pdf",
        classification="invoice",
        classification_confidence=0.97,
    )
    extraction_db.add(document)
    extraction_db.commit()

    fields_to_store = [
        ("invoice_number", "INV-2024-001", 0.99),
        ("supplier_name", "Tech Supplies Ltd", 0.94),
        ("invoice_date", "2026-10-21", 0.91),
        ("subtotal", "1000.00", 0.88),
        ("tax", "180.00", 0.85),
        ("total", "1180.00", 0.98),
    ]

    for field_name, value, conf in fields_to_store:
        rec = Extraction(
            document_id=document.id,
            field_name=field_name,
            value=value,
            confidence=conf,
        )
        extraction_db.add(rec)
    extraction_db.commit()

    stored_fields = (
        extraction_db.query(Extraction)
        .filter_by(document_id=document.id)
        .order_by(Extraction.field_name.asc())
        .all()
    )
    assert len(stored_fields) == 6
    field_names = [f.field_name for f in stored_fields]
    assert "invoice_number" in field_names
    assert "total" in field_names
    assert "tax" in field_names


def test_extraction_confidence_boundaries(extraction_db):
    """Test confidence bounds: 0.0 and 1.0 are valid; <0.0 or >1.0 are invalid."""
    document = Document(
        organization_id="org-123",
        uploaded_by="user-123",
        filename="boundary.pdf",
        file_type="application/pdf",
        file_size=512,
        storage_path="uploads/boundary.pdf",
    )
    extraction_db.add(document)
    extraction_db.commit()

    # Lower bound exact: 0.0
    rec_zero = Extraction(
        document_id=document.id,
        field_name="unclear_field",
        value="unknown",
        confidence=0.0,
    )
    extraction_db.add(rec_zero)
    extraction_db.commit()
    assert rec_zero.confidence == 0.0

    # Upper bound exact: 1.0
    rec_one = Extraction(
        document_id=document.id,
        field_name="verified_field",
        value="verified",
        confidence=1.0,
    )
    extraction_db.add(rec_one)
    extraction_db.commit()
    assert rec_one.confidence == 1.0

    # Below lower bound: -0.01
    rec_neg = Extraction(
        document_id=document.id,
        field_name="negative_conf",
        value="bad",
        confidence=-0.01,
    )
    extraction_db.add(rec_neg)
    with pytest.raises(IntegrityError):
        extraction_db.commit()
    extraction_db.rollback()

    # Above upper bound: 1.01
    rec_high = Extraction(
        document_id=document.id,
        field_name="high_conf",
        value="bad",
        confidence=1.01,
    )
    extraction_db.add(rec_high)
    with pytest.raises(IntegrityError):
        extraction_db.commit()
    extraction_db.rollback()


def test_extraction_timestamp_updates(extraction_db):
    """Verify created_at and updated_at behavior."""
    document = Document(
        organization_id="org-123",
        uploaded_by="user-123",
        filename="ts.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="uploads/ts.pdf",
    )
    extraction_db.add(document)
    extraction_db.commit()

    record = Extraction(
        document_id=document.id,
        field_name="status",
        value="draft",
        confidence=0.8,
    )
    extraction_db.add(record)
    extraction_db.commit()

    initial_created = record.created_at
    initial_updated = record.updated_at
    assert initial_created is not None
    assert initial_updated is not None

    time.sleep(0.01)
    record.value = "final"
    extraction_db.commit()
    extraction_db.refresh(record)

    assert record.value == "final"
    assert record.updated_at >= initial_updated


def test_extraction_crud_helpers(extraction_db):
    """Test app.crud.extraction helper functions."""
    document = Document(
        organization_id="org-crud",
        uploaded_by="user-crud",
        filename="crud_test.pdf",
        file_type="application/pdf",
        file_size=2048,
        storage_path="uploads/crud_test.pdf",
        classification="invoice",
    )
    extraction_db.add(document)
    extraction_db.commit()

    # Test create_extraction
    e1 = create_extraction(
        extraction_db,
        document.id,
        ExtractionCreate(field_name="item_name", value="Widget A", confidence=0.92),
    )
    assert e1.id is not None
    assert e1.field_name == "item_name"

    # Test create_extractions_bulk
    bulk = [
        ExtractionCreate(field_name="quantity", value="5", confidence=0.95),
        ExtractionCreate(field_name="unit_price", value="10.00", confidence=0.89),
    ]
    created_bulk = create_extractions_bulk(extraction_db, document.id, bulk)
    assert len(created_bulk) == 2

    # Test get_extractions_by_document
    all_exts = get_extractions_by_document(extraction_db, document.id)
    assert len(all_exts) == 3

    # Test get_document_extractions_summary
    summary = get_document_extractions_summary(extraction_db, document.id)
    assert summary is not None
    assert summary.document_id == document.id
    assert summary.document_type == "invoice"
    assert summary.fields["item_name"] == "Widget A"
    assert summary.fields["quantity"] == "5"
    assert summary.confidence["unit_price"] == pytest.approx(0.89)

    # Test delete_extractions_by_document
    deleted_count = delete_extractions_by_document(extraction_db, document.id)
    assert deleted_count == 3
    assert len(get_extractions_by_document(extraction_db, document.id)) == 0


def test_extraction_enforces_unique_field_per_document(extraction_db):
    """Enforce UniqueConstraint uq_extractions_document_field: same doc cannot have duplicate field_name."""
    document = Document(
        organization_id="org-unique",
        uploaded_by="user-unique",
        filename="unique_test.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="uploads/unique_test.pdf",
    )
    extraction_db.add(document)
    extraction_db.commit()

    rec1 = Extraction(
        document_id=document.id,
        field_name="tax_id",
        value="TAX-123",
        confidence=0.95,
    )
    extraction_db.add(rec1)
    extraction_db.commit()

    # Attempt to insert another extraction with the same field_name for the same document
    rec2 = Extraction(
        document_id=document.id,
        field_name="tax_id",
        value="TAX-456",
        confidence=0.90,
    )
    extraction_db.add(rec2)
    with pytest.raises(IntegrityError):
        extraction_db.commit()
    extraction_db.rollback()

    # Verify only the first record remains
    saved = extraction_db.query(Extraction).filter_by(document_id=document.id).all()
    assert len(saved) == 1
    assert saved[0].value == "TAX-123"


def test_extraction_allows_same_field_name_across_different_documents(extraction_db):
    """Different documents may have extractions with the same field_name."""
    doc1 = Document(
        organization_id="org-1",
        uploaded_by="user-1",
        filename="doc1.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="uploads/doc1.pdf",
    )
    doc2 = Document(
        organization_id="org-2",
        uploaded_by="user-2",
        filename="doc2.pdf",
        file_type="application/pdf",
        file_size=2048,
        storage_path="uploads/doc2.pdf",
    )
    extraction_db.add_all([doc1, doc2])
    extraction_db.commit()

    ext1 = Extraction(
        document_id=doc1.id,
        field_name="invoice_total",
        value="100.00",
        confidence=0.95,
    )
    ext2 = Extraction(
        document_id=doc2.id,
        field_name="invoice_total",
        value="250.00",
        confidence=0.92,
    )
    extraction_db.add_all([ext1, ext2])
    extraction_db.commit()

    saved_doc1 = extraction_db.query(Extraction).filter_by(document_id=doc1.id).all()
    saved_doc2 = extraction_db.query(Extraction).filter_by(document_id=doc2.id).all()
    assert len(saved_doc1) == 1
    assert saved_doc1[0].value == "100.00"
    assert len(saved_doc2) == 1
    assert saved_doc2[0].value == "250.00"


def test_create_extraction_rejects_duplicate_field_and_rolls_back(extraction_db):
    """CRUD create_extraction rejects duplicate field and leaves session clean."""
    document = Document(
        organization_id="org-crud-dup",
        uploaded_by="user-crud-dup",
        filename="crud_dup.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="uploads/crud_dup.pdf",
    )
    extraction_db.add(document)
    extraction_db.commit()

    e1 = create_extraction(
        extraction_db,
        document.id,
        ExtractionCreate(field_name="vat", value="20%", confidence=0.90),
    )
    assert e1.id is not None

    with pytest.raises(IntegrityError):
        create_extraction(
            extraction_db,
            document.id,
            ExtractionCreate(field_name="vat", value="21%", confidence=0.85),
        )

    # Session is usable without PendingRollbackError
    exts = get_extractions_by_document(extraction_db, document.id)
    assert len(exts) == 1
    assert exts[0].value == "20%"


def test_create_extraction_rejects_nonexistent_document(extraction_db):
    """CRUD create_extraction rejects nonexistent document_id."""
    with pytest.raises(IntegrityError):
        create_extraction(
            extraction_db,
            "nonexistent-document-id",
            ExtractionCreate(field_name="field", value="val", confidence=0.8),
        )

    # Session remains valid
    assert len(get_extractions_by_document(extraction_db, "nonexistent-document-id")) == 0


def test_create_extractions_bulk_rollback_on_any_invalid_record(extraction_db):
    """Bulk creation must roll back entire batch if any record fails validation or constraints."""
    document = Document(
        organization_id="org-bulk",
        uploaded_by="user-bulk",
        filename="bulk.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="uploads/bulk.pdf",
    )
    extraction_db.add(document)
    extraction_db.commit()

    # Batch where 2 records are valid and 1 violates DB confidence check constraint (confidence > 1.0)
    batch_with_invalid_confidence = [
        ExtractionCreate(field_name="valid_1", value="A", confidence=0.9),
        ExtractionCreate.model_construct(field_name="invalid_conf", value="B", confidence=1.5),
        ExtractionCreate(field_name="valid_2", value="C", confidence=0.8),
    ]

    with pytest.raises(IntegrityError):
        create_extractions_bulk(extraction_db, document.id, batch_with_invalid_confidence)

    # Verify atomic rollback: none of the records in the batch are persisted
    stored = get_extractions_by_document(extraction_db, document.id)
    assert len(stored) == 0

    # Batch with duplicate field_name within the batch
    batch_with_duplicate = [
        ExtractionCreate(field_name="dup_field", value="first", confidence=0.9),
        ExtractionCreate(field_name="dup_field", value="second", confidence=0.85),
    ]

    with pytest.raises(IntegrityError):
        create_extractions_bulk(extraction_db, document.id, batch_with_duplicate)

    # Verify again nothing was persisted
    assert len(get_extractions_by_document(extraction_db, document.id)) == 0

    # Empty batch returns empty list safely
    assert create_extractions_bulk(extraction_db, document.id, []) == []
