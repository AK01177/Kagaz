"""
QA-03: Integration tests — Upload → Classify Flow
===================================================

This is the **core integration-test file for QA-03**.  It exercises the
real Upload → Text Extraction → Classification pipeline end-to-end, with
only the external OpenRouter HTTP call mocked to return deterministic
responses based on the document text content.

Covers:

* Upload a PDF ➜ classification assigns the correct category based on
  content (financial, academic, HR, general).
* Text extraction is actually invoked on the uploaded PDF (pypdf).
* Classification result is persisted in metadata.
* The ``POST /{document_id}/classify`` reclassify endpoint works.
* Classification failures degrade gracefully (status remains UPLOADED,
  category set to ``unknown``).
* Manual classification correction via PATCH endpoint.
"""

import json

import httpx
import pytest

from services.classification import ClassificationError
from storage.document_storage import DocumentStorage
from .conftest import (
    _OpenRouterMock,
    make_pdf,
    upload_document,
)


# ---------------------------------------------------------------------------
# Upload triggers classification
# ---------------------------------------------------------------------------

class TestUploadClassifyIntegration:
    """The upload endpoint must extract text from the PDF and classify it."""

    def test_upload_invoice_classified_as_financial(self, client, invoice_pdf):
        body = upload_document(client, invoice_pdf, "inv.pdf")["body"]
        assert body["status"] == "CLASSIFIED"
        assert body["category"] == "financial"
        assert 0.0 < body["confidence"] <= 1.0

    def test_upload_transcript_classified_as_academics(self, client, transcript_pdf):
        body = upload_document(client, transcript_pdf, "trans.pdf")["body"]
        assert body["status"] == "CLASSIFIED"
        assert body["category"] == "academics"

    def test_upload_resume_classified_as_hr(self, client, resume_pdf):
        body = upload_document(client, resume_pdf, "cv.pdf")["body"]
        assert body["status"] == "CLASSIFIED"
        assert body["category"] == "hr_documents"

    def test_upload_generic_text_classified_as_general(self, client, sample_pdf):
        body = upload_document(client, sample_pdf, "misc.pdf")["body"]
        assert body["status"] == "CLASSIFIED"
        assert body["category"] == "general_confidential"

    def test_classification_result_persisted_in_metadata(
        self, client, invoice_pdf, storage_dir
    ):
        body = upload_document(client, invoice_pdf, "inv.pdf")["body"]
        meta = json.loads(
            (storage_dir / "metadata" / f"{body['document_id']}.json").read_text()
        )
        assert meta["category"] == "financial"
        assert meta["confidence"] == body["confidence"]
        assert meta["status"] == "CLASSIFIED"

    def test_text_extraction_feeds_into_classification(self, client, storage_dir):
        """Verify the mock receives the extracted text from the uploaded PDF."""
        _OpenRouterMock.reset()
        pdf = make_pdf("Invoice #99 — total amount $1000")
        upload_document(client, pdf, "inv.pdf")

        captured_texts = _OpenRouterMock.get_captured_texts()
        # The mock should have been called with extracted text from the PDF.
        assert len(captured_texts) >= 1
        assert "Invoice #99" in captured_texts[-1] or "invoice" in captured_texts[-1].lower()


# ---------------------------------------------------------------------------
# Reclassify endpoint
# ---------------------------------------------------------------------------

class TestReclassifyEndpoint:
    """POST /api/documents/{document_id}/classify re-extracts and reclassifies."""

    def test_reclassify_returns_updated_classification(
        self, client, invoice_pdf, storage_dir
    ):
        doc_id = upload_document(client, invoice_pdf, "inv.pdf")["body"]["document_id"]

        resp = client.post(f"/api/documents/{doc_id}/classify")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "CLASSIFIED"
        assert body["category"] == "financial"
        assert 0.0 < body["confidence"] <= 1.0

    def test_reclassify_updates_persisted_metadata(
        self, client, invoice_pdf, storage_dir
    ):
        doc_id = upload_document(client, invoice_pdf)["body"]["document_id"]
        client.post(f"/api/documents/{doc_id}/classify")

        meta = json.loads(
            (storage_dir / "metadata" / f"{doc_id}.json").read_text()
        )
        assert meta["status"] == "CLASSIFIED"
        assert meta["category"] == "financial"

    def test_reclassify_nonexistent_document_returns_404(self, client):
        resp = client.post("/api/documents/doc_does_not_exist/classify")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Classification failure during upload
# ---------------------------------------------------------------------------

class TestClassificationFailureDuringUpload:
    """When the external classifier fails, the upload still succeeds but
    with degraded metadata (category=unknown, confidence=0.0)."""

    def test_upload_succeeds_with_unknown_category_on_classification_error(
        self, client, sample_pdf, monkeypatch
    ):
        _OpenRouterMock.inject_failure(
            httpx.RequestError("Simulated network timeout")
        )

        body = upload_document(client, sample_pdf)["body"]
        # Upload itself should not fail — only classification degrades.
        assert body["document_id"].startswith("doc_")
        assert body["category"] == "unknown"
        assert body["confidence"] == 0.0

    def test_degraded_metadata_persisted_on_classification_failure(
        self, client, sample_pdf, storage_dir, monkeypatch
    ):
        _OpenRouterMock.inject_failure(
            httpx.RequestError("Simulated provider failure")
        )

        body = upload_document(client, sample_pdf)["body"]
        meta = json.loads(
            (storage_dir / "metadata" / f"{body['document_id']}.json").read_text()
        )
        assert meta["category"] == "unknown"
        assert meta["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Manual classification correction
# ---------------------------------------------------------------------------

class TestManualClassificationCorrection:
    """PATCH /api/documents/{document_id}/classification allows reviewers
    to correct a classification after upload."""

    def test_correct_classification_updates_category(self, client, invoice_pdf):
        doc_id = upload_document(client, invoice_pdf)["body"]["document_id"]

        resp = client.patch(
            f"/api/documents/{doc_id}/classification",
            json={"category": "academics", "notes": "Re-filed as academic"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["category"] == "academics"
        assert body["confidence"] == 1.0
        assert body["is_manually_corrected"] is True

    def test_correction_records_history(self, client, invoice_pdf):
        doc_id = upload_document(client, invoice_pdf)["body"]["document_id"]

        client.patch(
            f"/api/documents/{doc_id}/classification",
            json={"category": "hr_documents"},
        )
        resp = client.get(f"/api/documents/{doc_id}")
        body = resp.json()
        assert len(body["classification_history"]) == 1
        assert body["classification_history"][0]["previous_category"] == "financial"
        assert body["classification_history"][0]["updated_category"] == "hr_documents"

    def test_correct_then_reclassify_overwrites_manual_flag(
        self, client, invoice_pdf
    ):
        doc_id = upload_document(client, invoice_pdf)["body"]["document_id"]

        # Manually correct …
        client.patch(
            f"/api/documents/{doc_id}/classification",
            json={"category": "academics"},
        )

        # … then reclassify via the API.
        resp = client.post(f"/api/documents/{doc_id}/classify")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_manually_corrected"] is False
        assert body["category"] == "financial"  # back to AI classification
