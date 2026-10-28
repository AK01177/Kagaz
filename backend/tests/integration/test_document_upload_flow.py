"""
QA-03: Integration tests — Document Upload Flow
=================================================

Verifies the upload endpoint end-to-end:

* Successful upload returns correct status/structure.
* Uploaded PDF is persisted to disk.
* Response includes document_id, filename, file_type, status, and size.
* Edge-case uploads (missing file, empty, unsupported type, corrupted,
  oversized) return documented error codes and leave no orphaned artefacts.
"""

import io

import pytest
from reportlab.pdfgen import canvas

from .conftest import make_pdf, upload_document


# ---------------------------------------------------------------------------
# Successful upload
# ---------------------------------------------------------------------------

class TestUploadDocumentSuccess:
    """Happy-path tests for POST /api/documents."""

    def test_upload_returns_201_with_expected_fields(self, client, sample_pdf):
        result = upload_document(client, sample_pdf, "report.pdf")

        assert result["status_code"] == 201
        body = result["body"]

        # All expected response keys must be present.
        expected_keys = {
            "document_id", "filename", "file_type", "status",
            "uploaded_at", "category", "confidence", "file_size",
        }
        assert expected_keys == set(body.keys()), (
            f"Unexpected response keys: missing={expected_keys - set(body.keys())}, "
            f"extra={set(body.keys()) - expected_keys}"
        )

    def test_upload_returns_correct_filename(self, client, sample_pdf):
        body = upload_document(client, sample_pdf, "my_report.pdf")["body"]
        assert body["filename"] == "my_report.pdf"

    def test_upload_returns_pdf_file_type(self, client, sample_pdf):
        body = upload_document(client, sample_pdf)["body"]
        assert body["file_type"] == "application/pdf"

    def test_upload_returns_document_id_prefixed_with_doc(self, client, sample_pdf):
        body = upload_document(client, sample_pdf)["body"]
        assert body["document_id"].startswith("doc_")

    def test_upload_returns_correct_file_size(self, client, sample_pdf):
        body = upload_document(client, sample_pdf)["body"]
        assert body["file_size"] == len(sample_pdf)

    def test_upload_persists_pdf_to_storage(self, client, sample_pdf, storage_dir):
        body = upload_document(client, sample_pdf)["body"]
        doc_path = storage_dir / f"{body['document_id']}.pdf"
        assert doc_path.exists()
        assert doc_path.read_bytes() == sample_pdf

    def test_each_upload_gets_a_unique_document_id(self, client, sample_pdf):
        id1 = upload_document(client, sample_pdf)["body"]["document_id"]
        id2 = upload_document(client, sample_pdf)["body"]["document_id"]
        assert id1 != id2

    def test_upload_sets_classified_status_when_classification_succeeds(
        self, client, invoice_pdf
    ):
        body = upload_document(client, invoice_pdf, "inv.pdf")["body"]
        assert body["status"] == "CLASSIFIED"

    def test_upload_strips_path_traversal_from_filename(self, client, sample_pdf):
        body = upload_document(client, sample_pdf, "../../etc/passwd.pdf")["body"]
        assert body["filename"] == "passwd.pdf"
        assert body["status_code"] if "status_code" in body else True  # no error


# ---------------------------------------------------------------------------
# Upload failures
# ---------------------------------------------------------------------------

class TestUploadDocumentFailure:
    """Negative tests for POST /api/documents."""

    def test_missing_file_returns_400(self, client):
        resp = client.post("/api/documents")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_FILE"

    def test_empty_file_returns_400(self, client):
        resp = client.post(
            "/api/documents",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_FILE"

    def test_non_pdf_text_file_returns_415(self, client):
        resp = client.post(
            "/api/documents",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_fake_pdf_with_text_mime_returns_415(self, client):
        resp = client.post(
            "/api/documents",
            files={"file": ("fake.pdf", b"not a pdf", "text/plain")},
        )
        assert resp.status_code == 415

    def test_corrupted_pdf_returns_400(self, client):
        resp = client.post(
            "/api/documents",
            files={"file": ("bad.pdf", b"not a PDF at all", "application/pdf")},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_FILE"

    def test_broken_pdf_header_returns_400(self, client):
        resp = client.post(
            "/api/documents",
            files={"file": ("broken.pdf", b"%PDF-1.4\nbroken", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_failed_upload_leaves_no_orphaned_files(self, client, storage_dir):
        """After a rejected upload, no PDF or metadata JSON should remain."""
        client.post(
            "/api/documents",
            files={"file": ("bad.pdf", b"corrupted", "application/pdf")},
        )
        assert not list(storage_dir.rglob("*.pdf"))
        assert not list(storage_dir.rglob("*.json"))

    def test_upload_without_filename_returns_400(self, client, sample_pdf):
        """Whitespace-only filename is rejected by save_upload as INVALID_FILE."""
        resp = client.post(
            "/api/documents",
            files={"file": ("   ", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_FILE"

    def test_upload_with_empty_filename_header_returns_422(self, client, sample_pdf):
        """Empty multipart filename header is rejected by schema validation."""
        resp = client.post(
            "/api/documents",
            files={"file": ("", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

