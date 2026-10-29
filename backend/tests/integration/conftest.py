"""
QA-03: Shared fixtures for integration tests.

Provides a FastAPI TestClient wired to isolated temporary storage and a
deterministic mock for the external OpenRouter classification API so that
integration tests exercise the real application routing, validation, file I/O,
text extraction (pypdf), and metadata persistence — without hitting paid
external services or requiring real API keys.
"""

import io
import json
import sys
import time
from pathlib import Path

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from main import app

# Ensure both module paths resolve to the exact same module in sys.modules
# regardless of whether imports use 'backend.tests.integration.conftest' or
# 'tests.integration.conftest'.
sys.modules.setdefault("tests.integration.conftest", sys.modules[__name__])
sys.modules.setdefault("backend.tests.integration.conftest", sys.modules[__name__])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JWT_SECRET = "test-secret-only-not-for-production-0123456789"


# ---------------------------------------------------------------------------
# Helper: deterministic PDF generation
# ---------------------------------------------------------------------------

def make_pdf(text: str = "QA-03 integration test document", pages: int = 1) -> bytes:
    """Create a minimal valid PDF containing *text* on *pages* pages."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for i in range(pages):
        c.drawString(72, 750, f"{text} — page {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def make_token(**overrides) -> str:
    """Create a signed JWT matching the ``require_submitter`` dependency."""
    claims = {
        "sub": "integration_user",
        "role": "SUBMITTER",
        "organization_id": "integration_org",
        "active": True,
        "iss": "kagaz",
        "aud": "kagaz-api",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


def make_reviewer_token(**overrides) -> str:
    """Create a signed JWT matching the ``require_reviewer`` dependency."""
    return make_token(sub="integration_reviewer", role="REVIEWER", **overrides)


# ---------------------------------------------------------------------------
# Mock: OpenRouter classification API
# ---------------------------------------------------------------------------

class _OpenRouterMock:
    """Intercept ``httpx.post`` calls to the OpenRouter API and return
    deterministic classification results based on the document text content.

    The mock inspects the ``state.document_text`` payload so that test PDFs
    with known marker strings yield a predictable category.  Unmapped text
    defaults to ``general_confidential``.
    """

    MARKERS = {
        "invoice": ("financial", 0.95),
        "receipt": ("financial", 0.92),
        "transcript": ("academics", 0.97),
        "resume": ("hr_documents", 0.93),
        "contract": ("general_confidential", 0.90),
    }

    # When set to a non-None exception, the next call will raise it instead of
    # returning a response.  Reset after raising.
    _failure: Exception | None = None
    calls: list[dict] = []

    @classmethod
    def inject_failure(cls, exc: Exception) -> None:
        cls._failure = exc

    @classmethod
    def reset(cls) -> None:
        cls._failure = None
        cls.calls = []

    @classmethod
    def get_captured_texts(cls) -> list[str]:
        return [c.get("document_text", "") for c in cls.calls]

    @classmethod
    def handler(cls, *args, **kwargs):
        payload = kwargs.get("json", {})
        text = ""
        if isinstance(payload, dict):
            state = payload.get("state", {})
            if isinstance(state, dict):
                text = state.get("document_text", "")

        cls.calls.append({
            "args": args,
            "kwargs": kwargs,
            "json": payload,
            "document_text": text,
        })

        if cls._failure is not None:
            exc = cls._failure
            cls._failure = None
            raise exc

        lower_text = text.lower()
        category = "general_confidential"
        confidence = 0.85

        for marker, (cat, conf) in cls.MARKERS.items():
            if marker in lower_text:
                category = cat
                confidence = conf
                break

        class _Resp:
            status_code = 200
            def json(self_inner):
                return {
                    "answers": {
                        "category": {
                            "choice": category,
                            "confidence": confidence,
                            "probabilities": {category: confidence},
                        }
                    }
                }
            def raise_for_status(self_inner):
                pass

        return _Resp()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage_dir(tmp_path):
    """Provide a fresh temporary directory used as DOCUMENT_STORAGE_DIR."""
    return tmp_path


@pytest.fixture()
def client(monkeypatch, storage_dir):
    """Yield a TestClient that:

    * uses *storage_dir* for document persistence,
    * authenticates requests with a valid JWT,
    * intercepts OpenRouter API calls via ``_OpenRouterMock``.
    """
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-integration-test-key")

    # Mock only the external HTTP call — not the application logic.
    monkeypatch.setattr(httpx, "post", _OpenRouterMock.handler)
    _OpenRouterMock.reset()

    with TestClient(app, headers={"Authorization": f"Bearer {make_token()}"}) as tc:
        yield tc


@pytest.fixture()
def reviewer_headers():
    """Return Authorization headers for an authenticated user with the REVIEWER role."""
    return {"Authorization": f"Bearer {make_reviewer_token()}"}


@pytest.fixture()
def reviewer_client(monkeypatch, storage_dir):
    """Yield a TestClient authenticated with the REVIEWER role."""
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-integration-test-key")

    monkeypatch.setattr(httpx, "post", _OpenRouterMock.handler)
    _OpenRouterMock.reset()

    with TestClient(app, headers={"Authorization": f"Bearer {make_reviewer_token()}"}) as tc:
        yield tc


@pytest.fixture()
def unauthenticated_client(monkeypatch, storage_dir):
    """TestClient without any Authorization header (dev-mode fallback)."""
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "kagaz")
    monkeypatch.setenv("JWT_AUDIENCE", "kagaz-api")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-integration-test-key")
    monkeypatch.setattr(httpx, "post", _OpenRouterMock.handler)
    _OpenRouterMock.reset()
    with TestClient(app) as tc:
        yield tc


@pytest.fixture()
def sample_pdf():
    """A small valid PDF with generic text."""
    return make_pdf("QA-03 integration test document")


@pytest.fixture()
def invoice_pdf():
    """A valid PDF whose text contains 'invoice' for classification routing."""
    return make_pdf("Invoice #12345 — Amount Due: $500.00")


@pytest.fixture()
def transcript_pdf():
    """A valid PDF whose text contains 'transcript' for academic classification."""
    return make_pdf("Academic Transcript — GPA 3.8 — Spring 2026")


@pytest.fixture()
def resume_pdf():
    """A valid PDF whose text contains 'resume' for HR classification."""
    return make_pdf("Resume — Jane Doe — Software Engineer")


def upload_document(client, pdf_bytes: bytes, filename: str = "test.pdf") -> dict:
    """Helper: upload a PDF and return the parsed JSON response body."""
    resp = client.post(
        "/api/documents",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    return {"status_code": resp.status_code, "body": resp.json()}
