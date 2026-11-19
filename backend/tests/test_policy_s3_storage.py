import boto3
import pytest
from moto import mock_aws

from app.models.document import Document
from storage.document_storage import DocumentNotFoundError
from storage.s3_policy_storage import S3PolicyStorage, get_policy_storage
from tests.test_policy_ingestion import _pages, _pdf, _token, policy_client  # noqa: F401

BUCKET = "kagaz-test-policies"


@pytest.fixture
def s3_bucket(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_POLICY_BUCKET", BUCKET)
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def test_store_resolve_and_delete_round_trip(s3_bucket, tmp_path):
    storage = S3PolicyStorage(BUCKET, "us-east-1")
    source = tmp_path / "p.pdf"
    source.write_bytes(b"hello")

    storage_path = storage.store(source, "doc_1", ".pdf")

    assert storage_path == f"s3://{BUCKET}/policy_sources/doc_1.pdf"
    assert storage.exists("doc_1")
    assert storage.resolve("doc_1").read_bytes() == b"hello"
    storage.delete("doc_1", ".pdf")
    assert not storage.exists("doc_1")
    with pytest.raises(DocumentNotFoundError):
        storage.resolve("doc_1")


def test_factory_uses_s3_only_when_bucket_is_configured(s3_bucket, monkeypatch):
    assert isinstance(get_policy_storage(), S3PolicyStorage)
    monkeypatch.delenv("S3_POLICY_BUCKET")
    assert not isinstance(get_policy_storage(), S3PolicyStorage)


def test_ingest_stores_source_in_s3_and_indexes(policy_client, s3_bucket, monkeypatch):  # noqa: F811
    client, session = policy_client
    seen = {}

    def fake_extract(path):
        seen["bytes"] = path.read_bytes()
        return _pages("Policy clause: expenses require approval.")

    monkeypatch.setattr("services.policy_ingestion.extract_policy_pages", fake_extract)
    monkeypatch.setattr(
        "services.policy_ingestion.create_embeddings",
        lambda chunks: [[0.0] * 1536 for _ in chunks],
    )

    response = client.post(
        "/api/policies/ingest",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
        data={"policy_name": "Expense Policy", "version": "v1"},
        files={"file": ("expense-policy.pdf", _pdf(), "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "ACTIVE"
    document = session.query(Document).one()
    key = f"policy_sources/{document.id}.pdf"
    assert document.storage_path == f"s3://{BUCKET}/{key}"
    assert s3_bucket.get_object(Bucket=BUCKET, Key=key)["Body"].read() == seen["bytes"]


def test_rejected_upload_leaves_nothing_in_s3(policy_client, s3_bucket):  # noqa: F811
    client, session = policy_client

    response = client.post(
        "/api/policies/ingest",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
        data={"policy_name": "Bad", "version": "v1"},
        files={"file": ("bad.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert s3_bucket.list_objects_v2(Bucket=BUCKET).get("KeyCount", 0) == 0
