import io
import json
import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from main import app
from services.extraction import extract_text
from services import upload
from storage.document_storage import DocumentStorage

SECRET = "test-secret-only-not-for-production-0123456789"


def token(**overrides):
    return jwt.encode({
        "sub": "user_1", "role": "SUBMITTER", "organization_id": "org_1",
        "active": True, "iss": "kagaz", "aud": "kagaz-api",
        "iat": int(time.time()), "exp": int(time.time()) + 300, **overrides,
    }, SECRET, algorithm="HS256")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")
    
    from services.classification import ClassificationResult, DocumentCategory
    monkeypatch.setattr("services.upload.classify_document", lambda text: ClassificationResult(category=DocumentCategory.INVOICE, confidence=0.95))
    
    with TestClient(app, headers={"Authorization": f"Bearer {token()}"}) as client:
        yield client


@pytest.fixture
def pdf():
    stream = io.BytesIO()
    document = canvas.Canvas(stream)
    document.drawString(72, 800, "Upload integration test")
    document.save()
    return stream.getvalue()


def test_upload_persists_and_can_be_extracted(client, pdf, tmp_path):
    response = client.post("/api/documents", files={"file": ("invoice.pdf", pdf, "application/pdf")},
                           data={"organization_id": "forged_org"})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"document_id", "filename", "file_type", "status", "uploaded_at", "category", "confidence", "file_size"}
    assert body["status"] == "CLASSIFIED"
    assert body["category"] == "financial"
    assert body["confidence"] == 0.95
    assert body["file_size"] == len(pdf)
    document_id = body["document_id"]
    assert (tmp_path / f"{document_id}.pdf").read_bytes() == pdf
    metadata = json.loads((tmp_path / "metadata" / f"{document_id}.json").read_text())
    assert metadata["file_size"] == len(pdf)
    assert metadata["submitter_id"] == "user_1"
    assert metadata["organization_id"] == "org_1"
    assert metadata["category"] == "financial"
    assert metadata["confidence"] == 0.95
    assert "Upload integration test" in extract_text(document_id, DocumentStorage(tmp_path))
    another = client.post("/api/documents", files={"file": ("invoice.pdf", pdf, "application/pdf")})
    assert another.json()["document_id"] != document_id


@pytest.mark.parametrize("filename,content,mime,status", [
    ("empty.pdf", b"", "application/pdf", 400),
    ("fake.pdf", b"not a PDF", "application/pdf", 400),
    ("broken.pdf", b"%PDF-1.4\nbroken", "application/pdf", 400),
    ("note.txt", b"text", "text/plain", 415),
    ("fake.pdf", b"text", "text/plain", 415),
])
def test_invalid_uploads(client, tmp_path, filename, content, mime, status):
    response = client.post("/api/documents", files={"file": (filename, content, mime)})
    assert response.status_code == status
    assert "code" in response.json()["error"]
    assert not list(tmp_path.rglob("*.pdf"))
    assert not list(tmp_path.rglob("*.json"))


def test_missing_file(client):
    response = client.post("/api/documents")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE"


def test_oversized_upload_is_removed(client, pdf, monkeypatch, tmp_path):
    monkeypatch.setattr(upload, "MAX_UPLOAD_BYTES", len(pdf) - 1)
    response = client.post("/api/documents", files={"file": ("invoice.pdf", pdf, "application/pdf")})
    assert response.status_code == 413
    assert not list(tmp_path.rglob("*.pdf"))


def test_filename_cannot_control_storage_path(client, pdf, tmp_path):
    response = client.post("/api/documents", files={"file": ("../../invoice.pdf", pdf, "application/pdf")})
    assert response.status_code == 201
    assert response.json()["filename"] == "invoice.pdf"
    assert (tmp_path / f"{response.json()['document_id']}.pdf").is_file()


def test_metadata_failure_rolls_back_document(client, pdf, monkeypatch, tmp_path):
    original = Path.replace

    def fail_metadata(path, target):
        if path.name == "metadata.json":
            raise OSError("simulated storage failure")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", fail_metadata)
    response = client.post("/api/documents", files={"file": ("invoice.pdf", pdf, "application/pdf")})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "STORAGE_FAILURE"
    assert not list(tmp_path.rglob("*.pdf"))
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.parametrize("claims,status", [
    ({"exp": 1}, 401), ({"aud": "wrong"}, 401), ({"iss": "wrong"}, 401),
    ({"organization_id": ""}, 401), ({"role": "REVIEWER"}, 403),
    ({"active": False}, 403),
])
def test_rejects_invalid_identity(client, pdf, claims, status):
    response = client.post("/api/documents", headers={"Authorization": f"Bearer {token(**claims)}"},
                           files={"file": ("invoice.pdf", pdf, "application/pdf")})
    assert response.status_code == status
    assert "error" in response.json()


def test_allows_missing_authentication_in_dev_mode(client, pdf):
    response = client.post(
        "/api/documents",
        headers={"Authorization": ""},
        files={"file": ("auth.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201


def test_rejects_wrong_signature(client):
    forged = jwt.encode({"sub": "user_1"}, "different-secret-that-is-long-enough", algorithm="HS256")
    assert client.post("/api/documents", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_missing_secret_fails_closed(client, monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    assert client.post("/api/documents").status_code == 503
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("extra,status", [(0, 201), (1, 413)])
def test_file_size_boundary_with_multipart_overhead(client, pdf, extra, status):
    # Pad before the PDF header (after its signature line) to retain a readable
    # PDF rather than adding trailing bytes that hide its EOF marker.
    # A PDF comment can carry the padding; pypdf repairs the shifted xref.
    header, rest = pdf.split(b"\n", 1)
    padding = upload.MAX_UPLOAD_BYTES + extra - len(pdf) - 2
    content = header + b"\n%" + b" " * padding + b"\n" + rest
    assert len(content) == upload.MAX_UPLOAD_BYTES + extra
    response = client.post("/api/documents", files={"file": ("boundary.pdf", content, "application/pdf")})
    assert response.status_code == status


def test_correct_classification_success(client, pdf):
    # First upload a document
    upload_res = client.post("/api/documents", files={"file": ("invoice.pdf", pdf, "application/pdf")})
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document_id"]

    reviewer_headers = {"Authorization": f"Bearer {token(role='REVIEWER')}"}

    # Unauthorized submitter cannot correct classification
    unauth_res = client.patch(
        f"/api/documents/{doc_id}/classification",
        json={"category": "general_confidential"},
    )
    assert unauth_res.status_code == 403

    # Now correct its classification with reviewer token
    patch_res = client.patch(
        f"/api/documents/{doc_id}/classification",
        headers=reviewer_headers,
        json={"category": "general_confidential", "notes": "Reclassified by reviewer"},
    )
    assert patch_res.status_code == 200
    body = patch_res.json()
    assert body["category"] == "general_confidential"
    assert body["confidence"] == 1.0
    assert body["is_manually_corrected"] is True
    assert len(body["classification_history"]) == 1
    assert body["classification_history"][0]["previous_category"] == "financial"
    assert body["classification_history"][0]["updated_category"] == "general_confidential"
    assert body["classification_history"][0]["notes"] == "Reclassified by reviewer"

    # Verify GET returns updated data
    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["category"] == "general_confidential"
    assert get_res.json()["is_manually_corrected"] is True


def test_correct_classification_invalid_category(client, pdf):
    upload_res = client.post("/api/documents", files={"file": ("invoice.pdf", pdf, "application/pdf")})
    doc_id = upload_res.json()["document_id"]
    reviewer_headers = {"Authorization": f"Bearer {token(role='REVIEWER')}"}

    patch_res = client.patch(
        f"/api/documents/{doc_id}/classification",
        headers=reviewer_headers,
        json={"category": "non_existent_category"},
    )
    assert patch_res.status_code == 422
    assert "Invalid category" in patch_res.text


def test_correct_classification_not_found(client):
    reviewer_headers = {"Authorization": f"Bearer {token(role='REVIEWER')}"}
    patch_res = client.patch(
        "/api/documents/non_existent_doc_id/classification",
        headers=reviewer_headers,
        json={"category": "contract"},
    )
    assert patch_res.status_code == 404


# QA-02: Isolated backend unit tests

import io
import json
from pathlib import Path

import pytest
from fastapi import UploadFile
from reportlab.pdfgen import canvas
from starlette.datastructures import Headers

from services import upload
from services.classification import ClassificationError, ClassificationResult, DocumentCategory
from services.extraction import ExtractionError
from storage.document_storage import DocumentStorage


@pytest.fixture
def storage(tmp_path):
    return DocumentStorage(tmp_path)


@pytest.fixture
def user():
    return {"sub": "submitter_1", "organization_id": "org_1"}


@pytest.fixture
def pdf_bytes():
    stream = io.BytesIO()
    doc = canvas.Canvas(stream)
    doc.drawString(72, 780, "QA-02 unit test")
    doc.save()
    return stream.getvalue()


def make_upload(filename, content, mime="application/pdf"):
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": mime}),
    )


def mock_processing(monkeypatch):
    monkeypatch.setattr(upload, "extract_text", lambda document_id, storage: "Invoice 123")
    monkeypatch.setattr(
        upload,
        "classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.93),
    )


def test_service_persists_file_and_metadata(monkeypatch, storage, user, pdf_bytes):
    mock_processing(monkeypatch)

    result = upload.save_upload(make_upload("invoice.pdf", pdf_bytes), storage, user)

    assert result["status"] == "CLASSIFIED"
    assert result["category"] == "financial"
    assert result["confidence"] == 0.93
    assert result["file_size"] == len(pdf_bytes)
    assert result["uploaded_at"].endswith("Z")
    assert (storage.base_dir / f"{result['document_id']}.pdf").read_bytes() == pdf_bytes
    metadata_path = storage.base_dir / "metadata" / f"{result['document_id']}.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["filename"] == "invoice.pdf"
    assert metadata["file_type"] == "application/pdf"
    assert metadata["file_size"] == len(pdf_bytes)
    assert metadata["submitter_id"] == "submitter_1"
    assert metadata["organization_id"] == "org_1"
    assert metadata["storage_path"] == str((storage.base_dir / f"{result['document_id']}.pdf").resolve())


def test_service_removes_path_components_from_filename(monkeypatch, storage, user, pdf_bytes):
    mock_processing(monkeypatch)

    result = upload.save_upload(make_upload(r"C:\user\invoices\invoice.pdf", pdf_bytes), storage, user)

    assert result["filename"] == "invoice.pdf"
    assert (storage.base_dir / f"{result['document_id']}.pdf").is_file()


@pytest.mark.parametrize("filename", [None, "", "   ", "bad\x00name.pdf"])
def test_service_rejects_invalid_filename(storage, user, filename):
    with pytest.raises(upload.UploadError) as exc:
        upload.save_upload(make_upload(filename, b"example"), storage, user)

    assert exc.value.status_code == 400
    assert exc.value.code == "INVALID_FILE"
    assert not list(storage.base_dir.rglob("*.json"))


@pytest.mark.parametrize("filename,mime", [("doc.txt", "text/plain"), ("doc.pdf", "image/png")])
def test_service_rejects_unsupported_or_mismatched_type(storage, user, filename, mime):
    with pytest.raises(upload.UploadError) as exc:
        upload.save_upload(make_upload(filename, b"invalid", mime), storage, user)

    assert exc.value.status_code == 415
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"
    assert not list(storage.base_dir.rglob("*.json"))


@pytest.mark.parametrize(
    "filename,content,mime",
    [
        ("fake.png", b"not a png", "image/png"),
        ("fake.jpeg", b"not a jpeg", "image/jpeg"),
        ("fake.pdf", b"not a pdf", "application/pdf"),
    ],
)
def test_service_rejects_invalid_file_content(storage, user, filename, content, mime):
    with pytest.raises(upload.UploadError) as exc:
        upload.save_upload(make_upload(filename, content, mime), storage, user)

    assert exc.value.status_code == 400
    assert exc.value.code == "INVALID_FILE"
    assert not list(storage.base_dir.glob("doc_*"))


def test_service_rejects_upload_beyond_limit(monkeypatch, storage, user):
    monkeypatch.setattr(upload, "MAX_UPLOAD_BYTES", 10)

    with pytest.raises(upload.UploadError) as exc:
        upload.save_upload(make_upload("invoice.pdf", b"x" * 11), storage, user)

    assert exc.value.status_code == 413
    assert exc.value.code == "FILE_TOO_LARGE"
    assert not list(storage.base_dir.glob("doc_*"))


def test_service_keeps_upload_when_classification_fails(monkeypatch, storage, user, pdf_bytes):
    monkeypatch.setattr(upload, "extract_text", lambda document_id, storage: "Invoice text")

    def fail_classification(text):
        raise ClassificationError("provider unavailable")

    monkeypatch.setattr(upload, "classify_document", fail_classification)

    result = upload.save_upload(make_upload("invoice.pdf", pdf_bytes), storage, user)

    assert result["status"] == "UPLOADED"
    assert result["category"] == "unknown"
    assert result["confidence"] == 0.0
    assert (storage.base_dir / f"{result['document_id']}.pdf").is_file()
    metadata = json.loads((storage.base_dir / "metadata" / f"{result['document_id']}.json").read_text())
    assert metadata["status"] == "UPLOADED"
    assert metadata["category"] == "unknown"


def test_service_skips_classification_when_extraction_fails(monkeypatch, storage, user, pdf_bytes):
    def fail_extraction(document_id, storage):
        raise ExtractionError("cannot read document")

    def unexpected_classification(text):
        pytest.fail("classification must not run after extraction fails")

    monkeypatch.setattr(upload, "extract_text", fail_extraction)
    monkeypatch.setattr(upload, "classify_document", unexpected_classification)

    result = upload.save_upload(make_upload("invoice.pdf", pdf_bytes), storage, user)

    assert result["status"] == "UPLOADED"
    assert result["category"] == "unknown"
    assert result["confidence"] == 0.0


def test_service_rolls_back_document_on_metadata_write_failure(monkeypatch, storage, user, pdf_bytes):
    mock_processing(monkeypatch)
    original_replace = Path.replace

    def replace_with_metadata_failure(source, target):
        if source.name == "metadata.json":
            raise OSError("simulated metadata storage failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", replace_with_metadata_failure)

    with pytest.raises(upload.UploadError) as exc:
        upload.save_upload(make_upload("invoice.pdf", pdf_bytes), storage, user)

    assert exc.value.status_code == 500
    assert exc.value.code == "STORAGE_FAILURE"
    assert not list(storage.base_dir.glob("doc_*"))
    assert not list((storage.base_dir / "metadata").glob("*.json"))
