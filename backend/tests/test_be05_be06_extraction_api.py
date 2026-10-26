"""
Tests for BE-05 (persist extraction results) and BE-06 (GET /extract API).

Uses SQLite in-memory engine — no PostgreSQL required.
"""
import io
import json
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.document import Document
from app.models.extraction import Extraction
from app.schemas.extraction import ExtractionCreate, DocumentExtractionsResponse
from app.crud.extraction import (
    create_extractions_bulk,
    get_document_extractions_summary,
    delete_extractions_by_document,
)
from services.extraction_persistence import persist_extraction_result, ExtractionPersistenceError

# ---------------------------------------------------------------------------
# SQLite test engine (mirrors test_extraction.py pattern)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(conn, _record):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def document(db):
    """Insert a minimal document record for FK references."""
    doc = Document(
        organization_id="org_test",
        uploaded_by="user_test",
        filename="invoice.pdf",
        file_type="application/pdf",
        file_size=1024,
        storage_path="uploads/invoice.pdf",
        classification="financial",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# BE-05: persist_extraction_result
# ---------------------------------------------------------------------------

class _FakeExtraction:
    """Minimal BaseDocumentExtraction-compatible stub."""

    def to_flat_dict(self):
        return {"invoice_number": "INV-001", "supplier_name": "Acme Ltd", "total_amount": None}

    def get_field_confidences(self):
        return {"invoice_number": 0.97, "supplier_name": 0.93, "total_amount": 0.0}


def test_persist_extraction_stores_non_none_fields(db, document):
    records = persist_extraction_result(db, document.id, _FakeExtraction())
    assert len(records) == 2  # total_amount is None — skipped
    field_names = {r.field_name for r in records}
    assert field_names == {"invoice_number", "supplier_name"}


def test_persist_extraction_idempotent(db, document):
    """Calling persist twice replaces the first set cleanly."""
    persist_extraction_result(db, document.id, _FakeExtraction())
    persist_extraction_result(db, document.id, _FakeExtraction())

    rows = db.query(Extraction).filter(Extraction.document_id == document.id).all()
    assert len(rows) == 2  # no duplicates


def test_persist_extraction_skips_empty_list_fields(db, document):
    class _EmptyListExtraction:
        def to_flat_dict(self):
            return {"skills": []}

        def get_field_confidences(self):
            return {"skills": 0.0}

    records = persist_extraction_result(db, document.id, _EmptyListExtraction())
    assert records == []


def test_persist_extraction_converts_list_to_string(db, document):
    class _ListExtraction:
        def to_flat_dict(self):
            return {"skills": ["Python", "SQL", "Docker"]}

        def get_field_confidences(self):
            return {"skills": 0.88}

    records = persist_extraction_result(db, document.id, _ListExtraction())
    assert len(records) == 1
    assert records[0].field_name == "skills"
    assert records[0].value == "Python, SQL, Docker"


# ---------------------------------------------------------------------------
# BE-05: get_document_extractions_summary
# ---------------------------------------------------------------------------

def test_get_extractions_summary_returns_none_for_missing_document(db):
    result = get_document_extractions_summary(db, "nonexistent_doc_id")
    assert result is None


def test_get_extractions_summary_returns_empty_dicts_when_no_fields(db, document):
    result = get_document_extractions_summary(db, document.id)
    assert isinstance(result, DocumentExtractionsResponse)
    assert result.fields == {}
    assert result.confidence == {}


def test_get_extractions_summary_returns_stored_fields(db, document):
    create_extractions_bulk(db, document.id, [
        ExtractionCreate(field_name="invoice_number", value="INV-042", confidence=0.97),
        ExtractionCreate(field_name="supplier_name", value="Acme Ltd", confidence=0.93),
    ])

    result = get_document_extractions_summary(db, document.id)
    assert result is not None
    assert result.document_id == document.id
    assert result.document_type == "financial"
    assert result.fields["invoice_number"] == "INV-042"
    assert result.confidence["supplier_name"] == pytest.approx(0.93)


# ---------------------------------------------------------------------------
# BE-06: GET /api/documents/{id}/extract (JSON-store backend)
# ---------------------------------------------------------------------------

SECRET = "test-secret-only-not-for-production-0123456789"


def _token(**overrides):
    return jwt.encode({
        "sub": "reviewer_1", "role": "REVIEWER", "organization_id": "org_1",
        "active": True, "iss": "kagaz", "aud": "kagaz-api",
        "iat": int(time.time()), "exp": int(time.time()) + 300, **overrides,
    }, SECRET, algorithm="HS256")


def _pdf_bytes():
    stream = io.BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(72, 800, "Invoice test")
    c.save()
    return stream.getvalue()


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")

    from services.classification import ClassificationResult, DocumentCategory
    monkeypatch.setattr(
        "services.upload.classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.95),
    )

    from main import app
    with TestClient(app) as client:
        yield client, tmp_path


def test_get_extract_returns_404_for_unknown_document(api_client):
    client, _ = api_client
    res = client.get(
        "/api/documents/nonexistent/extract",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert res.status_code == 404


def test_get_extract_returns_empty_fields_when_not_yet_extracted(api_client):
    client, tmp_path = api_client

    # Upload a document (no auth needed in dev mode for POST)
    pdf = _pdf_bytes()
    upload_res = client.post(
        "/api/documents",
        files={"file": ("invoice.pdf", pdf, "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document_id"]

    # Retrieve extraction (reviewer token)
    extract_res = client.get(
        f"/api/documents/{doc_id}/extract",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert extract_res.status_code == 200
    body = extract_res.json()
    assert body["document_id"] == doc_id
    assert body["fields"] == {}
    assert body["confidence"] == {}


def test_get_extract_returns_fields_when_metadata_has_extractions(api_client):
    client, tmp_path = api_client

    pdf = _pdf_bytes()
    upload_res = client.post(
        "/api/documents",
        files={"file": ("invoice.pdf", pdf, "application/pdf")},
    )
    doc_id = upload_res.json()["document_id"]

    # Manually inject extraction data into the JSON metadata
    metadata_path = tmp_path / "metadata" / f"{doc_id}.json"
    with open(metadata_path, "r") as f:
        meta = json.load(f)
    meta["extracted_fields"] = {"invoice_number": "INV-999", "supplier_name": "Test Co"}
    meta["extracted_confidence"] = {"invoice_number": 0.98, "supplier_name": 0.91}
    with open(metadata_path, "w") as f:
        json.dump(meta, f)

    extract_res = client.get(
        f"/api/documents/{doc_id}/extract",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert extract_res.status_code == 200
    body = extract_res.json()
    assert body["fields"]["invoice_number"] == "INV-999"
    assert body["confidence"]["supplier_name"] == pytest.approx(0.91)
    assert body["status"] == "EXTRACTED"


def test_get_extract_requires_reviewer_role(api_client):
    client, tmp_path = api_client

    pdf = _pdf_bytes()
    upload_res = client.post("/api/documents", files={"file": ("invoice.pdf", pdf, "application/pdf")})
    doc_id = upload_res.json()["document_id"]

    # Submitter token should be rejected
    submitter_token = jwt.encode({
        "sub": "s1", "role": "SUBMITTER", "organization_id": "org_1",
        "active": True, "iss": "kagaz", "aud": "kagaz-api",
        "iat": int(time.time()), "exp": int(time.time()) + 300,
    }, SECRET, algorithm="HS256")

    res = client.get(
        f"/api/documents/{doc_id}/extract",
        headers={"Authorization": f"Bearer {submitter_token}"},
    )
    assert res.status_code == 403
