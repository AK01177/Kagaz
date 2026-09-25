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
    assert set(body) == {"document_id", "filename", "file_type", "status", "uploaded_at"}
    assert body["status"] == "UPLOADED"
    document_id = body["document_id"]
    assert (tmp_path / f"{document_id}.pdf").read_bytes() == pdf
    metadata = json.loads((tmp_path / "metadata" / f"{document_id}.json").read_text())
    assert metadata["file_size"] == len(pdf)
    assert metadata["submitter_id"] == "user_1"
    assert metadata["organization_id"] == "org_1"
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


def test_requires_authentication(client):
    client.headers.pop("Authorization")
    response = client.post("/api/documents")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


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
