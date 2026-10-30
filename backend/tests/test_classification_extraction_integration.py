"""
QA-06: Classification to Extraction Integration Tests.
Verifies the complete backend pipeline hand-off:
Upload -> Text extraction -> Classification -> Structured extraction -> Persistence -> API response.

Covers:
- Test 1: Successful complete pipeline
- Test 2: Classification happens before structured extraction (execution order)
- Test 3: Correct category is passed into structured extraction
- Test 4: Structured extraction is persisted (fields, confidence, metadata)
- Test 5: API response schema (GET /api/documents/{id}/extract)
- Test 6: Text extraction failure handling
- Test 7: Classification failure handling
- Test 8: Structured extraction failure handling
- Test 9: Persistence failure handling
- Test 10: Missing or unsupported document category handling
- Test 11: Manual classification correction re-extraction hand-off
- Test 12: Database extraction persistence integration
"""
import io
import json
import time
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.document import Document
from app.models.extraction import Extraction
from app.schemas.extraction import (
    ExtractedField,
    ExtractionCreate,
    InvoiceExtraction,
    ResumeExtraction,
)
from main import app
from services.classification import ClassificationError, ClassificationResult, DocumentCategory
from services.extraction import ExtractionError
from services.extraction_persistence import (
    ExtractionPersistenceError,
    persist_extraction_result,
)
from services.structured_extraction import (
    StructuredExtractionError,
    UnsupportedDocumentTypeError,
)
import services.upload as upload_module
from storage.document_storage import DocumentStorage

SECRET = "test-secret-qa06-classification-extraction-0123456789"


def _make_token(role: str = "SUBMITTER", sub: str = "user_qa06", org: str = "org_qa06"):
    return jwt.encode(
        {
            "sub": sub,
            "role": role,
            "organization_id": org,
            "active": True,
            "iss": "kagaz",
            "aud": "kagaz-api",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        },
        SECRET,
        algorithm="HS256",
    )


def _sample_invoice_pdf():
    stream = io.BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(72, 800, "INVOICE #INV-2026-901")
    c.drawString(72, 780, "Date: 2026-10-30")
    c.drawString(72, 760, "Supplier: Global Tech Corp")
    c.drawString(72, 740, "Total: $12500.00")
    c.save()
    return stream.getvalue()


def _sample_resume_pdf():
    stream = io.BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(72, 800, "Jane Doe - Senior Software Engineer")
    c.drawString(72, 780, "Email: jane.doe@example.com")
    c.drawString(72, 760, "Phone: +1-555-0199")
    c.drawString(72, 740, "Skills: Python, FastAPI, Docker, SQL")
    c.save()
    return stream.getvalue()


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")

    submitter_headers = {"Authorization": f"Bearer {_make_token(role='SUBMITTER')}"}
    reviewer_headers = {"Authorization": f"Bearer {_make_token(role='REVIEWER')}"}

    with TestClient(app) as client:
        yield {
            "client": client,
            "tmp_path": tmp_path,
            "submitter_headers": submitter_headers,
            "reviewer_headers": reviewer_headers,
            "storage": DocumentStorage(base_dir=tmp_path),
        }


# ---------------------------------------------------------------------------
# Test 1: Successful complete pipeline
# ---------------------------------------------------------------------------
def test_01_successful_complete_pipeline(test_env, monkeypatch):
    """
    Test 1: Upload a known document.
    Verify that upload succeeds, text extraction occurs, classification occurs,
    structured extraction occurs, metadata is persisted, and API returns expected status.
    """
    client = test_env["client"]
    tmp_path = test_env["tmp_path"]
    headers = test_env["submitter_headers"]

    mock_invoice = InvoiceExtraction(
        invoice_number=ExtractedField.present("INV-2026-901", confidence=0.99),
        invoice_date=ExtractedField.present("2026-10-30", confidence=0.95),
        supplier_name=ExtractedField.present("Global Tech Corp", confidence=0.97),
        total_amount=ExtractedField.present(12500.0, confidence=0.96),
    )

    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.95),
    )
    monkeypatch.setattr(
        upload_module,
        "extract_structured_fields",
        lambda text, doc_type: mock_invoice,
    )

    pdf = _sample_invoice_pdf()
    res = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("invoice.pdf", pdf, "application/pdf")},
    )

    assert res.status_code == 201
    body = res.json()
    doc_id = body["document_id"]
    assert body["status"] == "EXTRACTED"
    assert body["category"] == "financial"
    assert body["confidence"] == 0.95

    # Verify metadata on disk
    meta_path = tmp_path / "metadata" / f"{doc_id}.json"
    assert meta_path.exists()
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["status"] == "EXTRACTED"
    assert meta["category"] == "financial"
    assert meta["extracted_fields"]["invoice_number"] == "INV-2026-901"
    assert meta["extracted_fields"]["supplier_name"] == "Global Tech Corp"
    assert meta["extracted_fields"]["total_amount"] == 12500.0
    assert meta["extracted_confidence"]["invoice_number"] == 0.99


# ---------------------------------------------------------------------------
# Test 2: Classification happens before structured extraction
# ---------------------------------------------------------------------------
def test_02_classification_happens_before_structured_extraction(test_env, monkeypatch):
    """
    Test 2: Verify the exact order of operations.
    Text extraction completes first -> Classification completes next ->
    Structured extraction is called only after classification with the category.
    """
    client = test_env["client"]
    headers = test_env["submitter_headers"]

    call_order = []

    def tracking_extract_text(doc_id, storage):
        call_order.append("text_extraction")
        return "INVOICE #INV-100 Global Tech Corp"

    def tracking_classify(text):
        call_order.append("classification")
        return ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.94)

    def tracking_extract_structured(text, doc_type):
        call_order.append("structured_extraction")
        return InvoiceExtraction(
            invoice_number=ExtractedField.present("INV-100", confidence=0.98),
        )

    monkeypatch.setattr(upload_module, "extract_text", tracking_extract_text)
    monkeypatch.setattr(upload_module, "classify_document", tracking_classify)
    monkeypatch.setattr(upload_module, "extract_structured_fields", tracking_extract_structured)

    pdf = _sample_invoice_pdf()
    res = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("invoice.pdf", pdf, "application/pdf")},
    )
    assert res.status_code == 201

    assert call_order == ["text_extraction", "classification", "structured_extraction"]


# ---------------------------------------------------------------------------
# Test 3: Correct category is passed into structured extraction
# ---------------------------------------------------------------------------
def test_03_correct_category_is_passed_to_structured_extraction(test_env, monkeypatch):
    """
    Test 3: Verify the structured extraction function receives the category
    returned by classification, rather than a hardcoded value or default.
    """
    client = test_env["client"]
    headers = test_env["submitter_headers"]

    received_categories = []

    def mock_extract_structured(text, doc_type):
        received_categories.append(doc_type)
        if doc_type == "hr_documents":
            return ResumeExtraction(
                candidate_name=ExtractedField.present("Jane Doe", confidence=0.95),
            )
        return InvoiceExtraction(
            invoice_number=ExtractedField.present("INV-999", confidence=0.95),
        )

    # Scenario A: Financial document
    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.95),
    )
    monkeypatch.setattr(upload_module, "extract_structured_fields", mock_extract_structured)

    res_fin = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("invoice.pdf", _sample_invoice_pdf(), "application/pdf")},
    )
    assert res_fin.status_code == 201
    assert received_categories[-1] == "financial"

    # Scenario B: HR document
    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.HR_DOCUMENTS, confidence=0.91),
    )

    res_hr = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("resume.pdf", _sample_resume_pdf(), "application/pdf")},
    )
    assert res_hr.status_code == 201
    assert received_categories[-1] == "hr_documents"


# ---------------------------------------------------------------------------
# Test 4: Structured extraction is persisted
# ---------------------------------------------------------------------------
def test_04_structured_extraction_is_persisted(test_env, monkeypatch):
    """
    Test 4: Verify field names, values, and confidence scores are persisted
    in the metadata file, preserving existing metadata properties (file_size, etc.).
    """
    client = test_env["client"]
    tmp_path = test_env["tmp_path"]
    headers = test_env["submitter_headers"]

    mock_invoice = InvoiceExtraction(
        invoice_number=ExtractedField.present("INV-TEST-444", confidence=0.98),
        supplier_name=ExtractedField.present("Acme Supplies", confidence=0.92),
        total_amount=ExtractedField.present(450.75, confidence=0.89),
    )
    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.96),
    )
    monkeypatch.setattr(upload_module, "extract_structured_fields", lambda text, doc_type: mock_invoice)

    pdf = _sample_invoice_pdf()
    res = client.post("/api/documents", headers=headers, files={"file": ("invoice.pdf", pdf, "application/pdf")})
    doc_id = res.json()["document_id"]

    meta_file = tmp_path / "metadata" / f"{doc_id}.json"
    assert meta_file.exists()
    meta = json.loads(meta_file.read_text(encoding="utf-8"))

    # Field data
    assert meta["extracted_fields"]["invoice_number"] == "INV-TEST-444"
    assert meta["extracted_fields"]["supplier_name"] == "Acme Supplies"
    assert meta["extracted_fields"]["total_amount"] == 450.75
    # Confidences
    assert meta["extracted_confidence"]["invoice_number"] == 0.98
    assert meta["extracted_confidence"]["supplier_name"] == 0.92
    assert meta["extracted_confidence"]["total_amount"] == 0.89
    # Metadata preserved
    assert meta["document_id"] == doc_id
    assert meta["file_size"] == len(pdf)
    assert meta["submitter_id"] == "user_qa06"
    assert meta["organization_id"] == "org_qa06"


# ---------------------------------------------------------------------------
# Test 5: API response verification
# ---------------------------------------------------------------------------
def test_05_api_response_schema(test_env, monkeypatch):
    """
    Test 5: Call GET /api/documents/{id}/extract and verify the exact schema:
    - document_id
    - document_type
    - fields
    - confidence
    - status
    """
    client = test_env["client"]
    submitter_headers = test_env["submitter_headers"]
    reviewer_headers = test_env["reviewer_headers"]

    mock_invoice = InvoiceExtraction(
        invoice_number=ExtractedField.present("INV-API-555", confidence=0.97),
        supplier_name=ExtractedField.present("Nexus Corp", confidence=0.94),
        total_amount=ExtractedField.present(999.00, confidence=0.91),
    )
    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.95),
    )
    monkeypatch.setattr(upload_module, "extract_structured_fields", lambda text, doc_type: mock_invoice)

    res = client.post(
        "/api/documents",
        headers=submitter_headers,
        files={"file": ("invoice.pdf", _sample_invoice_pdf(), "application/pdf")},
    )
    doc_id = res.json()["document_id"]

    # Call extraction API
    extract_res = client.get(
        f"/api/documents/{doc_id}/extract",
        headers=reviewer_headers,
    )
    assert extract_res.status_code == 200
    data = extract_res.json()

    assert set(data.keys()) == {"document_id", "document_type", "fields", "confidence", "status"}
    assert data["document_id"] == doc_id
    assert data["document_type"] == "financial"
    assert data["status"] == "EXTRACTED"
    assert data["fields"]["invoice_number"] == "INV-API-555"
    assert data["confidence"]["supplier_name"] == pytest.approx(0.94)


# ---------------------------------------------------------------------------
# Test 6: Text extraction failure handling
# ---------------------------------------------------------------------------
def test_06_text_extraction_failure_prevents_structured_extraction(test_env, monkeypatch):
    """
    Test 6: Simulate text extraction failure.
    Verify error is handled safely and structured extraction is NOT called.
    """
    client = test_env["client"]
    headers = test_env["submitter_headers"]

    structured_mock = MagicMock()
    monkeypatch.setattr(
        upload_module,
        "extract_text",
        MagicMock(side_effect=ExtractionError("Unreadable document")),
    )
    monkeypatch.setattr(upload_module, "extract_structured_fields", structured_mock)

    res = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("corrupt.pdf", _sample_invoice_pdf(), "application/pdf")},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "UPLOADED"
    assert body["category"] == "unknown"
    assert body["confidence"] == 0.0

    structured_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Test 7: Classification failure handling
# ---------------------------------------------------------------------------
def test_07_classification_failure_prevents_structured_extraction(test_env, monkeypatch):
    """
    Test 7: Simulate classification failure.
    Verify error is handled consistently and structured extraction is NOT called.
    """
    client = test_env["client"]
    headers = test_env["submitter_headers"]

    structured_mock = MagicMock()
    monkeypatch.setattr(
        upload_module,
        "classify_document",
        MagicMock(side_effect=ClassificationError("Provider timeout")),
    )
    monkeypatch.setattr(upload_module, "extract_structured_fields", structured_mock)

    res = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("invoice.pdf", _sample_invoice_pdf(), "application/pdf")},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "UPLOADED"
    assert body["category"] == "unknown"

    structured_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Test 8: Structured extraction failure handling
# ---------------------------------------------------------------------------
def test_08_structured_extraction_failure_does_not_falsely_indicate_success(test_env, monkeypatch):
    """
    Test 8: Simulate structured extraction failure.
    Verify failure is handled clearly and metadata/API does NOT falsely report EXTRACTED.
    """
    client = test_env["client"]
    submitter_headers = test_env["submitter_headers"]
    reviewer_headers = test_env["reviewer_headers"]
    tmp_path = test_env["tmp_path"]

    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.92),
    )
    monkeypatch.setattr(
        upload_module,
        "extract_structured_fields",
        MagicMock(side_effect=StructuredExtractionError("LLM response malformed")),
    )

    res = client.post(
        "/api/documents",
        headers=submitter_headers,
        files={"file": ("invoice.pdf", _sample_invoice_pdf(), "application/pdf")},
    )
    assert res.status_code == 201
    body = res.json()
    doc_id = body["document_id"]
    # Retains CLASSIFIED rather than false EXTRACTED
    assert body["status"] == "CLASSIFIED"

    # Verify metadata on disk does not claim success
    meta = json.loads((tmp_path / "metadata" / f"{doc_id}.json").read_text(encoding="utf-8"))
    assert meta["status"] == "CLASSIFIED"
    assert "extracted_fields" not in meta

    # API response also reports CLASSIFIED with empty fields
    extract_res = client.get(f"/api/documents/{doc_id}/extract", headers=reviewer_headers)
    assert extract_res.status_code == 200
    extract_body = extract_res.json()
    assert extract_body["status"] == "CLASSIFIED"
    assert extract_body["fields"] == {}


# ---------------------------------------------------------------------------
# Test 9: Persistence failure handling
# ---------------------------------------------------------------------------
def test_09_persistence_failure_does_not_report_false_success(tmp_path, monkeypatch):
    """
    Test 9: Simulate database persistence failure.
    Verify the application rolls back or does not report EXTRACTED status.
    """
    mock_invoice = InvoiceExtraction(
        invoice_number=ExtractedField.present("INV-PERSIST-99", confidence=0.95),
    )
    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.92),
    )
    monkeypatch.setattr(upload_module, "extract_structured_fields", lambda text, doc_type: mock_invoice)

    # Create dummy upload and user
    from fastapi import UploadFile
    storage = DocumentStorage(base_dir=tmp_path)
    user = {"sub": "user_qa06", "organization_id": "org_qa06"}
    file = UploadFile(
        filename="invoice.pdf",
        file=io.BytesIO(_sample_invoice_pdf()),
        headers={"content-type": "application/pdf"},
    )

    # Fake db session that fails persistence
    fake_db = MagicMock()
    fake_db.query.side_effect = Exception("DB connection dropped")

    res = upload_module.save_upload(file, storage, user, db=fake_db)
    # The failure prevents status from becoming EXTRACTED
    assert res["status"] == "CLASSIFIED"

    # Stored metadata also does not claim EXTRACTED
    meta = json.loads((tmp_path / "metadata" / f"{res['document_id']}.json").read_text(encoding="utf-8"))
    assert meta["status"] == "CLASSIFIED"
    assert "extracted_fields" not in meta


# ---------------------------------------------------------------------------
# Test 10: Unsupported or missing category handling
# ---------------------------------------------------------------------------
def test_10_unsupported_category_handled_gracefully(test_env, monkeypatch):
    """
    Test 10: When a document type has no registered extraction schema,
    the pipeline catches UnsupportedDocumentTypeError safely and preserves CLASSIFIED status.
    """
    client = test_env["client"]
    headers = test_env["submitter_headers"]

    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.GENERAL_CONFIDENTIAL, confidence=0.85),
    )
    monkeypatch.setattr(
        upload_module,
        "extract_structured_fields",
        MagicMock(side_effect=UnsupportedDocumentTypeError("No schema for general_confidential")),
    )

    res = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("memo.pdf", _sample_invoice_pdf(), "application/pdf")},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "CLASSIFIED"
    assert body["category"] == "general_confidential"


# ---------------------------------------------------------------------------
# Test 11: Manual classification correction triggers re-extraction
# ---------------------------------------------------------------------------
def test_11_manual_correction_re_extracts_with_new_category(test_env, monkeypatch):
    """
    Test 11: When a reviewer corrects a document's classification (PATCH /classification),
    structured extraction is re-invoked with the updated category, updating stored fields.
    """
    client = test_env["client"]
    submitter_headers = test_env["submitter_headers"]
    reviewer_headers = test_env["reviewer_headers"]

    # Initial upload is misclassified as HR
    resume_mock = ResumeExtraction(
        candidate_name=ExtractedField.present("Old Name", confidence=0.8),
    )
    invoice_mock = InvoiceExtraction(
        invoice_number=ExtractedField.present("INV-CORRECTED-777", confidence=0.99),
        total_amount=ExtractedField.present(5400.0, confidence=0.95),
    )

    monkeypatch.setattr(
        upload_module,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.HR_DOCUMENTS, confidence=0.7),
    )
    monkeypatch.setattr(upload_module, "extract_structured_fields", lambda text, doc_type: resume_mock)

    upload_res = client.post(
        "/api/documents",
        headers=submitter_headers,
        files={"file": ("invoice.pdf", _sample_invoice_pdf(), "application/pdf")},
    )
    doc_id = upload_res.json()["document_id"]

    # Now mock structured extraction for when reviewer corrects to financial
    def mock_reextract(text, doc_type):
        if doc_type == "financial":
            return invoice_mock
        return resume_mock

    monkeypatch.setattr("api.documents.extract_structured_fields", mock_reextract)

    patch_res = client.patch(
        f"/api/documents/{doc_id}/classification",
        headers=reviewer_headers,
        json={"category": "financial", "notes": "Correction from HR to Financial"},
    )
    assert patch_res.status_code == 200
    patched_body = patch_res.json()
    assert patched_body["category"] == "financial"
    assert patched_body["status"] == "EXTRACTED"
    assert patched_body["extracted_fields"]["invoice_number"] == "INV-CORRECTED-777"

    # Verify GET /extract returns the newly extracted invoice fields
    extract_res = client.get(f"/api/documents/{doc_id}/extract", headers=reviewer_headers)
    assert extract_res.status_code == 200
    extract_body = extract_res.json()
    assert extract_body["document_type"] == "financial"
    assert extract_body["fields"]["invoice_number"] == "INV-CORRECTED-777"
    assert "candidate_name" not in extract_body["fields"]


# ---------------------------------------------------------------------------
# Test 12: Database persistence integration
# ---------------------------------------------------------------------------
def test_12_database_persistence_integration():
    """
    Test 12: Verify persist_extraction_result saves rows to the Extraction table,
    properly links foreign key to Document, and is idempotent on re-execution.
    """
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(conn, _record):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    db = Session()

    try:
        # Create parent document record
        doc = Document(
            organization_id="org_qa06",
            uploaded_by="user_qa06",
            filename="invoice.pdf",
            file_type="application/pdf",
            file_size=2048,
            storage_path="uploads/invoice.pdf",
            classification="financial",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        invoice_data = InvoiceExtraction(
            invoice_number=ExtractedField.present("INV-DB-100", confidence=0.98),
            supplier_name=ExtractedField.present("Supplier DB", confidence=0.94),
            total_amount=ExtractedField.present(3200.50, confidence=0.91),
        )

        # First run
        records = persist_extraction_result(db, doc.id, invoice_data)
        assert len(records) == 3
        rows = db.query(Extraction).filter(Extraction.document_id == doc.id).all()
        assert len(rows) == 3
        field_map = {r.field_name: r.value for r in rows}
        assert field_map["invoice_number"] == "INV-DB-100"
        assert field_map["supplier_name"] == "Supplier DB"
        assert field_map["total_amount"] == "3200.5"

        # Re-running extraction (idempotent replacement)
        updated_data = InvoiceExtraction(
            invoice_number=ExtractedField.present("INV-DB-101", confidence=0.99),
        )
        records_2 = persist_extraction_result(db, doc.id, updated_data)
        assert len(records_2) == 1
        rows_2 = db.query(Extraction).filter(Extraction.document_id == doc.id).all()
        assert len(rows_2) == 1
        assert rows_2[0].field_name == "invoice_number"
        assert rows_2[0].value == "INV-DB-101"
    finally:
        db.close()
        Base.metadata.drop_all(eng)

