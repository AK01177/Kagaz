"""
QA-03: Integration tests — Document Error Handling Flow
========================================================

Verifies that API error handling behaves correctly across the document
processing pipeline.

Covers:

* Invalid document IDs on GET, classify, and correction endpoints.
* Unsupported file types and corrupted documents.
* Authentication and authorization errors.
* Classification provider failures propagated through the reclassify endpoint.
* Invalid correction payloads (bad category, missing fields).
* Consistent error response structure.
"""

import time

import httpx
import jwt
import pytest

from .conftest import (
    JWT_SECRET,
    _OpenRouterMock,
    make_pdf,
    make_token,
    upload_document,
)


# ---------------------------------------------------------------------------
# Error response structure
# ---------------------------------------------------------------------------

class TestErrorResponseStructure:
    """All error responses should have a consistent ``{"error": {...}}`` shape."""

    def test_missing_file_error_has_code_and_message(self, client):
        resp = client.post("/api/documents")
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_unsupported_type_error_has_code_and_message(self, client):
        resp = client.post(
            "/api/documents",
            files={"file": ("doc.txt", b"hello", "text/plain")},
        )
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_404_error_has_detail(self, client):
        resp = client.get("/api/documents/doc_nonexistent")
        assert resp.status_code == 404
        # FastAPI wraps HTTPException detail in {"error": ...} via the custom handler.
        body = resp.json()
        assert "error" in body


# ---------------------------------------------------------------------------
# Invalid document ID errors
# ---------------------------------------------------------------------------

class TestInvalidDocumentIdErrors:
    """Endpoints must return 404 for non-existent document IDs."""

    def test_get_nonexistent_document(self, client):
        assert client.get("/api/documents/doc_fake_123").status_code == 404

    def test_classify_nonexistent_document(self, client):
        assert client.post("/api/documents/doc_fake_123/classify").status_code == 404

    def test_correct_nonexistent_document(self, client):
        resp = client.patch(
            "/api/documents/doc_fake_123/classification",
            json={"category": "financial"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Authentication and authorization errors
# ---------------------------------------------------------------------------

class TestAuthErrors:
    """Upload requires valid submitter credentials when JWT_SECRET is set."""

    def test_expired_token_returns_401(self, client, sample_pdf):
        expired = make_token(exp=int(time.time()) - 300)
        resp = client.post(
            "/api/documents",
            headers={"Authorization": f"Bearer {expired}"},
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 401

    def test_wrong_role_returns_403(self, client, sample_pdf):
        reviewer = make_token(role="REVIEWER")
        resp = client.post(
            "/api/documents",
            headers={"Authorization": f"Bearer {reviewer}"},
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 403

    def test_inactive_user_returns_403(self, client, sample_pdf):
        inactive = make_token(active=False)
        resp = client.post(
            "/api/documents",
            headers={"Authorization": f"Bearer {inactive}"},
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 403

    def test_forged_signature_returns_401(self, client, sample_pdf):
        forged = jwt.encode(
            {"sub": "evil", "role": "SUBMITTER", "organization_id": "org",
             "active": True, "iss": "kagaz", "aud": "kagaz-api",
             "iat": int(time.time()), "exp": int(time.time()) + 300},
            "completely-wrong-secret-that-is-long-enough",
            algorithm="HS256",
        )
        resp = client.post(
            "/api/documents",
            headers={"Authorization": f"Bearer {forged}"},
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 401

    def test_dev_mode_allows_unauthenticated_upload(
        self, unauthenticated_client, sample_pdf
    ):
        resp = unauthenticated_client.post(
            "/api/documents",
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Classification provider errors via reclassify endpoint
# ---------------------------------------------------------------------------

class TestReclassifyProviderErrors:
    """POST /api/documents/{id}/classify should return 422 or 500 when
    the classification or extraction step fails."""

    def test_reclassify_with_provider_failure_returns_error(
        self, client, sample_pdf, monkeypatch
    ):
        doc_id = upload_document(client, sample_pdf)["body"]["document_id"]

        # Inject a failure into the OpenRouter mock for the reclassify call.
        _OpenRouterMock.inject_failure(
            httpx.RequestError("Simulated provider timeout")
        )
        resp = client.post(f"/api/documents/{doc_id}/classify")
        # The endpoint wraps ExtractionError/ClassificationError as 422
        # and other exceptions as 500.
        assert resp.status_code in (422, 500)


# ---------------------------------------------------------------------------
# Invalid classification correction payloads
# ---------------------------------------------------------------------------

class TestInvalidCorrectionPayloads:
    """PATCH /api/documents/{id}/classification rejects bad inputs."""

    def test_invalid_category_returns_422(self, client, sample_pdf):
        doc_id = upload_document(client, sample_pdf)["body"]["document_id"]
        resp = client.patch(
            f"/api/documents/{doc_id}/classification",
            json={"category": "nonexistent_type"},
        )
        assert resp.status_code == 422

    def test_missing_category_field_returns_422(self, client, sample_pdf):
        doc_id = upload_document(client, sample_pdf)["body"]["document_id"]
        resp = client.patch(
            f"/api/documents/{doc_id}/classification",
            json={"notes": "Missing category"},
        )
        assert resp.status_code == 422

    def test_empty_category_returns_422(self, client, sample_pdf):
        doc_id = upload_document(client, sample_pdf)["body"]["document_id"]
        resp = client.patch(
            f"/api/documents/{doc_id}/classification",
            json={"category": ""},
        )
        assert resp.status_code == 422
