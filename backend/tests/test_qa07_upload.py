"""QA-07: upload, OCR dispatch, safe failures, and downstream text handoff.

Original synthetic cases use simulated OCR. Added user-document cases use actual OCR.
Missing OCR dependencies skip the added OCR cases; QA07_REQUIRE_OCR=1 makes them fail.
No running servers or AI API keys are needed.
QA07_REAL_OCR=1: also exercise actual PaddleOCR and scanned-PDF rendering.
Known missing product behavior is strict XFAIL, never counted as a pass.
"""
import io
import json
import os
import re
import shutil
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers
from storage.document_storage import DocumentStorage
from PIL import Image
from pypdf import PdfReader

from main import app
from services import extraction, ocr, structured_extraction, upload
from services.classification import (
    ClassificationResult, DocumentCategory, classify_document,
)

FIXTURES = Path(__file__).parent / "fixtures" / "qa07"
FORMATS = [
    ("invoice.pdf", "application/pdf"),
    ("scanned.pdf", "application/pdf"),
    ("invoice.png", "image/png"),
    ("invoice.jpg", "image/jpeg"),
    ("invoice.jpeg", "image/jpeg"),
]
OCR_FORMATS = FORMATS[1:]


@pytest.fixture
def expected():
    manifest = FIXTURES / "expected.json"
    assert manifest.exists(), "Run: python tests/qa07_generate_fixtures.py"
    return json.loads(manifest.read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch, tmp_path):
    # The endpoint's existing dependency is replaced only for test identities.
    # Production authentication is not changed.
    from api.auth import require_submitter, require_reviewer
    identity = {"sub": "qa07", "organization_id": "qa07-org", "role": "SUBMITTER"}
    saved = app.dependency_overrides.copy()
    app.dependency_overrides[require_submitter] = lambda: identity
    app.dependency_overrides[require_reviewer] = lambda: {**identity, "role": "REVIEWER"}
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


@pytest.fixture
def classifier(monkeypatch):
    spy = Mock(return_value=ClassificationResult(
        category=DocumentCategory.FINANCIAL, confidence=0.95,
    ))
    monkeypatch.setattr(upload, "classify_document", spy)
    return spy


def paddle_result(text):
    box = [[0, 0], [100, 0], [100, 50], [0, 50]]
    return [[[box, (line, 0.99)] for line in text.splitlines()]]


@pytest.fixture
def fake_ocr(monkeypatch, expected):
    # Keep real upload validation, PDF extraction and OCR dispatch.
    # Replace only the model and expensive scanned-page renderer.
    model = Mock()
    model.ocr.return_value = paddle_result(expected["text"])
    renderer = Mock()
    def render(path, **kwargs):
        assert Path(path).is_file()
        # Load the actual image embedded in our scanned PDF.
        page = PdfReader(path).pages[0]
        with Image.open(io.BytesIO(page.images[0].data)) as img:
            return [img.convert("RGB")]
    renderer.side_effect = render
    monkeypatch.setattr(ocr, "_PADDLE_AVAILABLE", True)
    monkeypatch.setattr(ocr, "_PDF2IMAGE_AVAILABLE", True)
    monkeypatch.setattr(ocr, "_ocr_instance", model)
    monkeypatch.setattr(ocr, "convert_from_path", renderer)
    return model, renderer


def post_file(client, name, mime):
    with (FIXTURES / name).open("rb") as file:
        return client.post("/api/documents", files={"file": (name, file, mime)})


def read_metadata(tmp_path, document_id):
    return json.loads((tmp_path / "metadata" / f"{document_id}.json").read_text())


def assert_invoice_text(text):
    assert "INV-007" in text
    assert "Test Company" in text
    assert "1250" in text


def test_fixture_files_are_real_and_scanned_pdf_has_no_text(expected):
    assert_invoice_text(PdfReader(FIXTURES / "invoice.pdf").pages[0].extract_text())
    scanned = PdfReader(FIXTURES / "scanned.pdf").pages[0]
    assert not (scanned.extract_text() or "").strip()
    assert len(scanned.images) == 1
    for name in ["invoice.png", "invoice.jpg", "invoice.jpeg"]:
        with Image.open(FIXTURES / name) as image:
            image.verify()


@pytest.mark.parametrize("name,mime", FORMATS)
def test_supported_upload_preserves_file_and_passes_text_to_classification(
    client, tmp_path, classifier, fake_ocr, name, mime,
):
    response = post_file(client, name, mime)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["file_type"] == mime
    assert body["filename"] == name
    assert body["status"] == "CLASSIFIED"
    assert body["category"] == "financial"
    assert body["confidence"] == pytest.approx(0.95)
    path = tmp_path / f"{body['document_id']}{Path(name).suffix}"
    assert path.read_bytes() == (FIXTURES / name).read_bytes()
    metadata = read_metadata(tmp_path, body["document_id"])
    assert metadata["file_size"] == (FIXTURES / name).stat().st_size
    assert metadata["organization_id"] == "qa07-org"
    classifier.assert_called_once()
    assert_invoice_text(classifier.call_args.args[0])
    model, renderer = fake_ocr
    if name == "invoice.pdf":
        model.ocr.assert_not_called()
        renderer.assert_not_called()
    else:
        model.ocr.assert_called_once()
        if name == "scanned.pdf":
            renderer.assert_called_once()
        else:
            renderer.assert_not_called()


@pytest.mark.parametrize("name,mime,status,code", [
    ("note.txt", "text/plain", 415, "UNSUPPORTED_FILE_TYPE"),
    ("empty.pdf", "application/pdf", 400, "INVALID_FILE"),
    ("broken.pdf", "application/pdf", 400, "INVALID_FILE"),
    ("broken.png", "image/png", 400, "INVALID_FILE"),
    ("broken.jpg", "image/jpeg", 400, "INVALID_FILE"),
    ("oversized.pdf", "application/pdf", 413, "FILE_TOO_LARGE"),
    ("invoice.png", "text/plain", 415, "UNSUPPORTED_FILE_TYPE"),
])
def test_invalid_upload_is_rejected_without_saved_document(
    client, tmp_path, classifier, name, mime, status, code,
):
    response = post_file(client, name, mime)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    classifier.assert_not_called()
    assert not list(tmp_path.glob("doc_*"))
    assert not list(tmp_path.rglob("*.json"))
    assert not list(tmp_path.glob("upload_*"))


@pytest.mark.parametrize("size_offset,expected_status", [(0, 201), (1, 413)])
def test_exact_size_boundary(client, monkeypatch, classifier, fake_ocr, size_offset, expected_status):
    data = (FIXTURES / "invoice.png").read_bytes()
    # Lower the service limit, exercising exact-limit/+1 behavior cheaply.
    monkeypatch.setattr(upload, "MAX_UPLOAD_BYTES", len(data))
    response = client.post("/api/documents", files={
        "file": ("boundary.png", data + b"x" * size_offset, "image/png"),
    })
    assert response.status_code == expected_status, response.text
    if size_offset:
        assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
        classifier.assert_not_called()


@pytest.mark.parametrize("name,mime", OCR_FORMATS)
def test_ocr_model_failure_is_controlled_and_file_remains(
    client, tmp_path, classifier, fake_ocr, name, mime,
):
    fake_ocr[0].ocr.side_effect = RuntimeError("QA07 simulated OCR failure")
    response = post_file(client, name, mime)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "UPLOADED"
    assert body["category"] == "unknown"
    assert body["confidence"] == 0.0
    classifier.assert_not_called()
    assert (tmp_path / f"{body['document_id']}{Path(name).suffix}").exists()
    assert read_metadata(tmp_path, body["document_id"])["status"] == "UPLOADED"
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("name,mime", OCR_FORMATS)
def test_missing_ocr_dependency_does_not_crash(
    client, monkeypatch, classifier, fake_ocr, name, mime,
):
    monkeypatch.setattr(ocr, "_PADDLE_AVAILABLE", False)
    response = post_file(client, name, mime)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "UPLOADED"
    assert response.json()["category"] == "unknown"
    classifier.assert_not_called()
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("name,mime", [("blank.png", "image/png"), ("scanned.pdf", "application/pdf")])
@pytest.mark.parametrize("ocr_output", [None, [], [[]]])
def test_empty_ocr_output_never_becomes_successful_classification(
    client, monkeypatch, tmp_path, fake_ocr, name, mime, ocr_output,
):
    fake_ocr[0].ocr.return_value = ocr_output
    # Use the real classifier's empty-input guard. No provider call is needed.
    monkeypatch.setattr(upload, "classify_document", classify_document)
    response = post_file(client, name, mime)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "UPLOADED"
    assert body["category"] == "unknown"
    assert body["confidence"] == 0.0
    assert read_metadata(tmp_path, body["document_id"])["status"] == "UPLOADED"


@pytest.mark.parametrize("name,mime", FORMATS)
def test_extracted_text_can_be_consumed_by_field_extraction(
    client, tmp_path, classifier, fake_ocr, expected, name, mime,
):
    response = post_file(client, name, mime)
    assert response.status_code == 201, response.text
    text = extraction.extract_text(
        response.json()["document_id"], upload.DocumentStorage(tmp_path),
    )
    sent_prompts = []
    def provider(request):
        assert request.url.host == "openrouter.ai"
        payload = json.loads(request.content)
        prompt = payload["messages"][-1]["content"]
        sent_prompts.append(prompt)
        assert text in prompt
        assert_invoice_text(prompt)
        fields = {key: expected[key] for key in ["invoice_number", "supplier_name", "total_amount"]}
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(fields)}}],
        })
    # A local transport replaces the model provider. No external request.
    with httpx.Client(transport=httpx.MockTransport(provider)) as provider_client:
        result = structured_extraction.extract_structured_fields(
            text, response.json()["category"],
            api_key="qa07-fake-key", client=provider_client,
        )
    assert len(sent_prompts) == 1
    assert result.invoice_number.value == "INV-007"
    assert result.supplier_name.value == "Test Company"
    assert result.total_amount.value == 1250
    # Component compatibility only: this test explicitly invokes extraction.
    # The next test tracks the missing automatic upload-to-fields wiring.



def test_upload_automatically_runs_and_persists_field_extraction(
    client, monkeypatch, classifier, expected,
):
    from app.schemas.extraction import get_extraction_schema
    result = structured_extraction.parse_and_validate_fields(
        {key: expected[key] for key in ["invoice_number", "supplier_name", "total_amount"]},
        get_extraction_schema("financial"),
    )
    spy = Mock(return_value=result)
    monkeypatch.setattr(structured_extraction, "extract_structured_fields", spy)
    monkeypatch.setattr(extraction, "extract_structured_fields", spy)
    # Also cover a future direct import at the upload call site.
    monkeypatch.setattr(upload, "extract_structured_fields", spy, raising=False)
    response = post_file(client, "invoice.pdf", "application/pdf")
    assert response.status_code == 201, response.text
    assert spy.call_count == 1, "Upload never called structured field extraction"
    args = spy.call_args
    text = args.args[0] if args.args else args.kwargs["text"]
    assert_invoice_text(text)
    fields_response = client.get(f"/api/documents/{response.json()['document_id']}/extract")
    assert fields_response.status_code == 200
    fields = fields_response.json()["fields"]
    assert fields["invoice_number"] == "INV-007"
    assert float(fields["total_amount"]) == 1250


@pytest.mark.parametrize("name,mime", [("truncated.png", "image/png"), ("truncated.jpg", "image/jpeg")])
@pytest.mark.xfail(strict=True, reason=(
    "QA07 product gap: image validation checks only magic bytes; corrupt signed images are accepted."
))
def test_truncated_image_with_valid_signature_is_rejected(client, classifier, fake_ocr, name, mime):
    response = post_file(client, name, mime)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "INVALID_FILE"
    classifier.assert_not_called()


@pytest.mark.skipif(os.environ.get("QA07_REAL_OCR") != "1", reason=(
    "Optional real OCR: set QA07_REAL_OCR=1 with compatible PaddleOCR, models, pdf2image and Poppler."
))
@pytest.mark.parametrize("name,mime", OCR_FORMATS)
def test_real_ocr_extracts_fixture_invoice(client, classifier, name, mime):
    # No fake_ocr fixture: actual OCR dependencies, rendering and models.
    # An explicitly enabled run FAILS when dependencies/model execution fail.
    assert ocr._PADDLE_AVAILABLE, "Install compatible PaddleOCR and PaddlePaddle"
    if name == "scanned.pdf":
        assert ocr._PDF2IMAGE_AVAILABLE, "Install pdf2image and put Poppler on PATH"
    response = post_file(client, name, mime)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "CLASSIFIED", response.text
    classifier.assert_called_once()
    recognized = classifier.call_args.args[0].upper()
    assert "INV-007" in recognized, recognized
    assert "1250" in recognized, recognized


# Additional original user documents: real extraction, no mocked OCR.
REAL_FIXTURES = FIXTURES
REAL_DOCUMENTS = [
    ("template_invoice.pdf", "application/pdf", False,
     {"invoice": r"INV\s*[-\u2013]?\s*1218", "supplier": r"Johnson\s+Solutions",
      "total": r"1[,\s]?085[.,]00"}),
    ("scanned_receipt.pdf", "application/pdf", True,
     {"invoice": r"MYACC\s*[-\u2013]?\s*716", "total": r"3[,\s]?800[.,]00"}),
    ("invoice_image.png", "image/png", True,
     {"invoice": r"INV\s*[-\u2013]?\s*005", "supplier": r"Ad4tech\s+Material\s+LLC",
      "total": r"1[,\s]?564[.,]00", "balance_due": r"1[,\s]?332[.,]00"}),
    ("receipt_photo.png", "image/png", True,
     {"invoice": r"MYACC\s*[-\u2013]?\s*716", "total": r"3[,\s]?800[.,]00"}),
]
REAL_IDS = [doc[0] for doc in REAL_DOCUMENTS]


def real_fixture_path(name):
    path = REAL_FIXTURES / name
    assert path.is_file(), f"Missing fixture: {path}. Copy the entire supplied fixture folder."
    return path


def require_real_ocr(name, needs_ocr):
    if not needs_ocr:
        return
    missing = []
    if not ocr._PADDLE_AVAILABLE:
        missing.append("compatible PaddleOCR/PaddlePaddle and models")
    if name.endswith(".pdf"):
        if not ocr._PDF2IMAGE_AVAILABLE:
            missing.append("pdf2image")
        if not shutil.which("pdftoppm"):
            missing.append("Poppler (pdftoppm on PATH)")
    if missing:
        message = "BLOCKED - real OCR requires " + ", ".join(missing)
        if os.environ.get("QA07_REQUIRE_OCR") == "1":
            pytest.fail(message)
        pytest.skip(message)


def check_real_values(text, patterns):
    assert text.strip(), "Extraction returned no text"
    for field, pattern in patterns.items():
        assert re.search(pattern, text, re.IGNORECASE), (
            f"{field} not recognized. Expected /{pattern}/. Actual text:\n{text}"
        )


@pytest.mark.parametrize("name,mime,needs_ocr,patterns", REAL_DOCUMENTS, ids=REAL_IDS)
def test_original_document_is_readable(name, mime, needs_ocr, patterns):
    path = real_fixture_path(name)
    assert 0 < path.stat().st_size <= upload.MAX_UPLOAD_BYTES
    if path.suffix == ".pdf":
        reader = PdfReader(path)
        assert not reader.is_encrypted
        assert len(reader.pages) >= 1
    else:
        with Image.open(path) as image:
            assert image.width > 0 and image.height > 0
            image.verify()


def test_pdf_paths_are_correctly_identified():
    embedded = "\n".join(page.extract_text() or "" for page in PdfReader(
        real_fixture_path("template_invoice.pdf")).pages)
    assert "INV-1218" in embedded
    scanned = PdfReader(real_fixture_path("scanned_receipt.pdf"))
    assert not "\n".join(page.extract_text() or "" for page in scanned.pages).strip()
    assert any(page.images for page in scanned.pages)


@pytest.mark.parametrize("name,mime,needs_ocr,patterns", REAL_DOCUMENTS, ids=REAL_IDS)
def test_real_document_text_matches_expected_invoice(tmp_path, name, mime, needs_ocr, patterns):
    path = real_fixture_path(name)
    require_real_ocr(name, needs_ocr)
    storage = DocumentStorage(tmp_path)
    storage.base_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, storage.base_dir / ("real_doc" + path.suffix))
    # Actual application extraction. No OCR functions are patched.
    text = extraction.extract_text("real_doc", storage)
    (tmp_path / "recognized_text.txt").write_text(text, encoding="utf-8")
    print(f"\n{name}:\n{text}\n")
    check_real_values(text, patterns)


@pytest.mark.parametrize("name,mime,needs_ocr,patterns", REAL_DOCUMENTS, ids=REAL_IDS)
def test_upload_passes_real_extracted_text_to_classifier(
    tmp_path, monkeypatch, name, mime, needs_ocr, patterns,
):
    path = real_fixture_path(name)
    require_real_ocr(name, needs_ocr)
    received = []

    def local_classifier(text):
        # Verify the actual extracted text; replace only the external AI classifier.
        check_real_values(text, patterns)
        received.append(text)
        return ClassificationResult(category=DocumentCategory.FINANCIAL, confidence=0.95)

    monkeypatch.setattr(upload, "classify_document", local_classifier)
    storage = DocumentStorage(tmp_path)
    file = UploadFile(
        file=io.BytesIO(path.read_bytes()), filename=name,
        headers=Headers({"content-type": mime}),
    )
    try:
        result = upload.save_upload(
            file, storage, {"sub": "qa07-real", "organization_id": "qa07-real-org"},
        )
    finally:
        file.file.close()
    assert result["status"] == "CLASSIFIED", result
    assert result["category"] == "financial"
    assert len(received) == 1
    saved = tmp_path / (result["document_id"] + path.suffix)
    assert saved.read_bytes() == path.read_bytes()
    metadata = json.loads((tmp_path / "metadata" / f"{result['document_id']}.json").read_text())
    assert metadata["file_size"] == path.stat().st_size
    assert metadata["filename"] == name
    assert metadata["organization_id"] == "qa07-real-org"
