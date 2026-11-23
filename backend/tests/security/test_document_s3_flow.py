"""Upload, download and read metadata with S3 storage enabled (no local copy of the file)."""
import io

import boto3
import pytest
from moto import mock_aws

from app.models.document import Document
from tests.security.conftest import SecurityWorld, make_valid_pdf_bytes

BUCKET = "kagaz-flow-documents"


@pytest.fixture
def s3_flow(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_DOCUMENT_BUCKET", BUCKET)
    monkeypatch.setattr("services.upload.classification_is_configured", lambda: False)
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def test_upload_goes_to_s3_and_metadata_to_the_database(client, security_world: SecurityWorld, db_session, s3_flow):
    headers = security_world.headers_for(security_world.submitter_a1)
    pdf = make_valid_pdf_bytes()

    response = client.post("/api/documents", files={"file": ("bill.pdf", io.BytesIO(pdf), "application/pdf")}, headers=headers)

    assert response.status_code == 201, response.text
    doc_id = response.json()["document_id"]
    keys = [o["Key"] for o in s3_flow.list_objects_v2(Bucket=BUCKET)["Contents"]]
    assert keys == [f"documents/{doc_id}.pdf"]
    assert not list(security_world.storage_dir.glob(f"{doc_id}.*"))  # nothing on local disk
    assert not (security_world.storage_dir / "metadata" / f"{doc_id}.json").exists()
    row = db_session.get(Document, doc_id)
    assert row.storage_path == f"s3://{BUCKET}/documents/{doc_id}.pdf"
    assert row.metadata_json["filename"] == "bill.pdf"

    meta = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert meta.status_code == 200 and meta.json()["filename"] == "bill.pdf"
    file_resp = client.get(f"/api/documents/{doc_id}/file", headers=headers)
    assert file_resp.status_code == 200 and file_resp.content == pdf
    assert file_resp.headers["content-type"] == "application/pdf"


def test_other_submitter_cannot_download_from_s3(client, security_world: SecurityWorld, s3_flow):
    owner = security_world.headers_for(security_world.submitter_a1)
    other = security_world.headers_for(security_world.submitter_a2)
    doc_id = client.post(
        "/api/documents", files={"file": ("bill.pdf", io.BytesIO(make_valid_pdf_bytes()), "application/pdf")}, headers=owner
    ).json()["document_id"]

    denied = client.get(f"/api/documents/{doc_id}/file", headers=other)

    assert denied.status_code == 403
