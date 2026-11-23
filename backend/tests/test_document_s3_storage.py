"""Document files in S3 and document metadata in the database."""
import boto3
import pytest
from moto import mock_aws

from services.document_metadata import discard_metadata, load_metadata, save_metadata
from storage.document_storage import DocumentNotFoundError, DocumentStorage
from storage.s3_document_storage import S3DocumentStorage, get_document_storage

BUCKET = "kagaz-test-documents"


@pytest.fixture
def s3_bucket(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_DOCUMENT_BUCKET", BUCKET)
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def test_s3_store_resolve_stream_and_delete(s3_bucket, tmp_path):
    storage = S3DocumentStorage(BUCKET, "us-east-1")
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF-bytes")

    assert storage.store(source, "doc_1", ".pdf") == f"s3://{BUCKET}/documents/doc_1.pdf"
    assert storage.resolve("doc_1").read_bytes() == b"%PDF-bytes"
    extension, body = storage.open_stream("doc_1")
    assert extension == ".pdf" and body.read() == b"%PDF-bytes"

    storage.delete("doc_1", ".pdf")
    assert storage.open_stream("doc_1") is None
    with pytest.raises(DocumentNotFoundError):
        storage.resolve("doc_1")


def test_factory_picks_s3_only_when_bucket_is_set(s3_bucket, monkeypatch):
    assert isinstance(get_document_storage(), S3DocumentStorage)
    monkeypatch.delenv("S3_DOCUMENT_BUCKET")
    assert isinstance(get_document_storage(), DocumentStorage)


def test_local_storage_store_and_delete(tmp_path):
    storage = DocumentStorage(str(tmp_path / "docs"))
    source = tmp_path / "a.png"
    source.write_bytes(b"png")

    path = storage.store(source, "doc_2", ".png")

    assert path.endswith("doc_2.png") and storage.resolve("doc_2").read_bytes() == b"png"
    storage.delete("doc_2", ".png")
    assert not storage.exists("doc_2")


def test_metadata_local_file_round_trip(tmp_path):
    storage = DocumentStorage(str(tmp_path))
    save_metadata("doc_3", {"status": "UPLOADED"}, storage)

    assert (tmp_path / "metadata" / "doc_3.json").exists()
    assert load_metadata("doc_3", storage) == {"status": "UPLOADED"}
    discard_metadata("doc_3", storage)
    assert load_metadata("doc_3", storage) is None


def test_metadata_with_s3_storage_uses_the_database_only(s3_bucket, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.base import Base
    from app.models.document import Document

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Document(id="doc_4", organization_id="o", uploaded_by="u", filename="a.pdf",
                    file_type="application/pdf", file_size=1, storage_path="s3://x"))
    db.commit()
    storage = S3DocumentStorage(BUCKET, "us-east-1")

    save_metadata("doc_4", {"category": "financial", "extracted_fields": {"total": "9"}}, storage, db)

    assert load_metadata("doc_4", storage, db)["extracted_fields"] == {"total": "9"}
    assert load_metadata("doc_5", storage, db) is None  # unknown document
    assert db.get(Document, "doc_4").metadata_json["category"] == "financial"
