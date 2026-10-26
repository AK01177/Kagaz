"""
Tests for BE-07: Multi-format upload validation.

Extends the existing upload test suite to cover PNG, JPG and JPEG uploads.
All image tests use real magic bytes so the validator passes.
"""
import io
import struct
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

SECRET = "test-secret-only-not-for-production-0123456789"


def _token(**overrides):
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
    monkeypatch.setattr(
        "services.upload.classify_document",
        lambda text: ClassificationResult(category=DocumentCategory.HR_DOCUMENTS, confidence=0.88),
    )
    # Stub extract_text for image files — OCR not available in test env
    monkeypatch.setattr(
        "services.upload.extract_text",
        lambda doc_id, storage: "sample ocr text",
    )

    from main import app
    with TestClient(app, headers={"Authorization": f"Bearer {_token()}"}) as c:
        yield c, tmp_path


def _pdf_bytes():
    stream = io.BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(72, 800, "Test document")
    c.save()
    return stream.getvalue()


def _png_bytes():
    """Minimal valid 1x1 PNG."""
    import zlib
    def _chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00\xff\x00\x00"  # filter byte + 1 RGB pixel
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


def _jpeg_bytes():
    """Minimal JPEG magic bytes (not a full valid JPEG, but enough for magic-byte check)."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 12


# ---------------------------------------------------------------------------
# Supported formats
# ---------------------------------------------------------------------------

def test_pdf_upload_still_works(client):
    c, tmp_path = client
    res = c.post("/api/documents", files={"file": ("report.pdf", _pdf_bytes(), "application/pdf")})
    assert res.status_code == 201
    assert res.json()["file_type"] == "application/pdf"


def test_png_upload_accepted(client):
    c, tmp_path = client
    png = _png_bytes()
    res = c.post("/api/documents", files={"file": ("scan.png", png, "image/png")})
    assert res.status_code == 201
    body = res.json()
    assert body["file_type"] == "image/png"
    assert body["filename"] == "scan.png"
    # Document stored with .png extension
    doc_id = body["document_id"]
    assert (tmp_path / f"{doc_id}.png").exists()


def test_jpg_upload_accepted(client):
    c, _ = client
    res = c.post("/api/documents", files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")})
    assert res.status_code == 201
    assert res.json()["file_type"] == "image/jpeg"


def test_jpeg_upload_accepted(client):
    c, _ = client
    res = c.post("/api/documents", files={"file": ("photo.jpeg", _jpeg_bytes(), "image/jpeg")})
    assert res.status_code == 201
    assert res.json()["file_type"] == "image/jpeg"


def test_png_with_octet_stream_mime_accepted(client):
    """Browser may send application/octet-stream for any binary file."""
    c, _ = client
    res = c.post("/api/documents", files={"file": ("scan.png", _png_bytes(), "application/octet-stream")})
    assert res.status_code == 201


# ---------------------------------------------------------------------------
# Unsupported / mismatched formats
# ---------------------------------------------------------------------------

def test_txt_file_rejected(client):
    c, _ = client
    res = c.post("/api/documents", files={"file": ("readme.txt", b"hello", "text/plain")})
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_docx_file_rejected(client):
    c, _ = client
    res = c.post("/api/documents", files={"file": ("doc.docx", b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res.status_code == 415


def test_extension_mime_mismatch_rejected(client):
    """A .png file sent with text/plain content-type should be rejected."""
    c, _ = client
    res = c.post("/api/documents", files={"file": ("image.png", _png_bytes(), "text/plain")})
    assert res.status_code == 415


def test_fake_png_content_rejected(client):
    """File with .png extension but not actual PNG magic bytes."""
    c, _ = client
    res = c.post("/api/documents", files={"file": ("fake.png", b"not a png file at all", "image/png")})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_FILE"


def test_empty_image_rejected(client):
    c, _ = client
    res = c.post("/api/documents", files={"file": ("empty.png", b"", "image/png")})
    assert res.status_code == 400


def test_oversized_image_rejected(client, monkeypatch):
    from services import upload
    monkeypatch.setattr(upload, "MAX_UPLOAD_BYTES", 10)
    c, _ = client
    res = c.post("/api/documents", files={"file": ("big.png", _png_bytes(), "image/png")})
    assert res.status_code == 413


# ---------------------------------------------------------------------------
# Metadata correctness
# ---------------------------------------------------------------------------

def test_image_metadata_stores_correct_file_type(client):
    import json
    c, tmp_path = client
    png = _png_bytes()
    res = c.post("/api/documents", files={"file": ("scan.png", png, "image/png")})
    doc_id = res.json()["document_id"]
    meta = json.loads((tmp_path / "metadata" / f"{doc_id}.json").read_text())
    assert meta["file_type"] == "image/png"
    assert meta["filename"] == "scan.png"
    assert meta["file_size"] == len(png)
