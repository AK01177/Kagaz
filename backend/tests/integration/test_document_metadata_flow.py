"""
QA-03: Integration tests — Document Metadata Persistence Flow
==============================================================

Verifies that the upload API creates correct JSON metadata on disk and
that the GET /api/documents/{document_id} endpoint returns it faithfully.

Covers:

* Metadata file creation upon successful upload.
* All expected metadata fields are present and accurate.
* Metadata retrieval via the GET endpoint.
* Failed uploads leave no partial metadata.
* Metadata isolation between independent uploads.
"""

import json

from .conftest import make_pdf, upload_document


# ---------------------------------------------------------------------------
# Metadata creation on upload
# ---------------------------------------------------------------------------

class TestMetadataCreation:
    """Verify that POST /api/documents persists a metadata JSON sidecar."""

    def test_upload_creates_metadata_json(self, client, sample_pdf, storage_dir):
        body = upload_document(client, sample_pdf)["body"]
        doc_id = body["document_id"]
        meta_path = storage_dir / "metadata" / f"{doc_id}.json"
        assert meta_path.exists(), "Metadata JSON file was not created on upload."

    def test_metadata_contains_expected_fields(self, client, invoice_pdf, storage_dir):
        body = upload_document(client, invoice_pdf, "inv.pdf")["body"]
        doc_id = body["document_id"]
        meta = json.loads(
            (storage_dir / "metadata" / f"{doc_id}.json").read_text(encoding="utf-8")
        )

        expected_fields = {
            "document_id", "filename", "file_type", "status", "uploaded_at",
            "category", "confidence", "file_size", "storage_path",
            "submitter_id", "organization_id",
        }
        assert expected_fields.issubset(set(meta.keys())), (
            f"Missing metadata fields: {expected_fields - set(meta.keys())}"
        )

    def test_metadata_matches_upload_response(self, client, invoice_pdf, storage_dir):
        body = upload_document(client, invoice_pdf, "inv.pdf")["body"]
        doc_id = body["document_id"]
        meta = json.loads(
            (storage_dir / "metadata" / f"{doc_id}.json").read_text(encoding="utf-8")
        )

        assert meta["document_id"] == body["document_id"]
        assert meta["filename"] == body["filename"]
        assert meta["file_type"] == body["file_type"]
        assert meta["status"] == body["status"]
        assert meta["category"] == body["category"]
        assert meta["confidence"] == body["confidence"]
        assert meta["file_size"] == body["file_size"]

    def test_metadata_records_submitter_identity(self, client, sample_pdf, storage_dir):
        body = upload_document(client, sample_pdf)["body"]
        meta = json.loads(
            (storage_dir / "metadata" / f"{body['document_id']}.json").read_text()
        )
        assert meta["submitter_id"] == "integration_user"
        assert meta["organization_id"] == "integration_org"

    def test_metadata_records_storage_path(self, client, sample_pdf, storage_dir):
        body = upload_document(client, sample_pdf)["body"]
        meta = json.loads(
            (storage_dir / "metadata" / f"{body['document_id']}.json").read_text()
        )
        assert meta["storage_path"].endswith(f"{body['document_id']}.pdf")

    def test_metadata_file_size_matches_pdf_bytes(self, client, sample_pdf, storage_dir):
        body = upload_document(client, sample_pdf)["body"]
        meta = json.loads(
            (storage_dir / "metadata" / f"{body['document_id']}.json").read_text()
        )
        assert meta["file_size"] == len(sample_pdf)


# ---------------------------------------------------------------------------
# Metadata retrieval via GET endpoint
# ---------------------------------------------------------------------------

class TestMetadataRetrieval:
    """Verify GET /api/documents/{document_id} reads the metadata JSON."""

    def test_get_document_returns_metadata(self, client, sample_pdf):
        doc_id = upload_document(client, sample_pdf)["body"]["document_id"]
        resp = client.get(f"/api/documents/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == doc_id
        assert data["filename"] == "test.pdf"

    def test_get_nonexistent_document_returns_404(self, client):
        resp = client.get("/api/documents/doc_nonexistent_12345")
        assert resp.status_code == 404

    def test_get_metadata_matches_persisted_json(self, client, invoice_pdf, storage_dir):
        body = upload_document(client, invoice_pdf, "inv.pdf")["body"]
        doc_id = body["document_id"]

        meta_disk = json.loads(
            (storage_dir / "metadata" / f"{doc_id}.json").read_text()
        )
        meta_api = client.get(f"/api/documents/{doc_id}").json()

        # The GET endpoint returns exactly what is in the JSON file.
        assert meta_api == meta_disk


# ---------------------------------------------------------------------------
# Metadata isolation
# ---------------------------------------------------------------------------

class TestMetadataIsolation:
    """Ensure each upload produces independent metadata."""

    def test_two_uploads_produce_independent_metadata(
        self, client, sample_pdf, invoice_pdf, storage_dir
    ):
        id1 = upload_document(client, sample_pdf, "a.pdf")["body"]["document_id"]
        id2 = upload_document(client, invoice_pdf, "b.pdf")["body"]["document_id"]

        meta1 = json.loads(
            (storage_dir / "metadata" / f"{id1}.json").read_text()
        )
        meta2 = json.loads(
            (storage_dir / "metadata" / f"{id2}.json").read_text()
        )

        assert meta1["document_id"] != meta2["document_id"]
        assert meta1["filename"] == "a.pdf"
        assert meta2["filename"] == "b.pdf"

    def test_failed_upload_leaves_no_metadata(self, client, storage_dir):
        client.post(
            "/api/documents",
            files={"file": ("bad.pdf", b"not a pdf", "application/pdf")},
        )
        assert not list((storage_dir / "metadata").rglob("*.json")) if (
            storage_dir / "metadata"
        ).exists() else True
