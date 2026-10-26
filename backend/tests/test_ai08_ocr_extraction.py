"""
Tests for AI-08: OCR and Multi-format Text Extraction (services/ocr.py).

Covers:
- Text-based PDF via extract_text() (unchanged pypdf path)
- Image-format dispatching without PaddleOCR (expects OcrExtractionError)
- Unsupported extension raises UnsupportedFormatError
- Empty / unreadable inputs produce controlled errors
- Normalisation helper

PaddleOCR and pdf2image are NOT required for these tests.  The OCR-specific
code paths are tested by verifying that the correct exceptions are raised
when the optional dependencies are absent (which is the case in CI).
"""
import io
import struct
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from reportlab.pdfgen import canvas

from services.ocr import (
    OcrExtractionError,
    UnsupportedFormatError,
    _normalize,
    extract_text_from_file,
)
from services.extraction import (
    SUPPORTED_EXTENSIONS,
    ExtractionError,
    UnsupportedDocumentTypeError,
    extract_text,
)
from storage.document_storage import DocumentStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path))
    y = 800
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()


def _png_bytes() -> bytes:
    def _chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00\xff\x00\x00"
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# ---------------------------------------------------------------------------
# AI-08: SUPPORTED_EXTENSIONS includes image formats
# ---------------------------------------------------------------------------

def test_supported_extensions_include_images():
    assert ".png" in SUPPORTED_EXTENSIONS
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".jpeg" in SUPPORTED_EXTENSIONS
    assert ".pdf" in SUPPORTED_EXTENSIONS


# ---------------------------------------------------------------------------
# AI-08: extract_text_from_file — unsupported extension
# ---------------------------------------------------------------------------

def test_extract_text_from_file_raises_for_unsupported_extension(tmp_path):
    f = tmp_path / "doc.docx"
    f.write_bytes(b"PK\x03\x04")
    with pytest.raises(UnsupportedFormatError):
        extract_text_from_file(f)


# ---------------------------------------------------------------------------
# AI-08: text-based PDF still works via extract_text
# ---------------------------------------------------------------------------

def test_extract_text_reads_text_based_pdf(tmp_path):
    storage = DocumentStorage(tmp_path)
    _write_pdf(tmp_path / "doc_text.pdf", ["Invoice total: 1000", "Supplier: Acme"])
    text = extract_text("doc_text", storage)
    assert "Invoice total" in text
    assert "Acme" in text


# ---------------------------------------------------------------------------
# AI-08: image file raises ExtractionError when PaddleOCR not available
# ---------------------------------------------------------------------------

def test_extract_text_raises_for_image_when_paddle_unavailable(tmp_path):
    """Without PaddleOCR installed, image extraction should raise ExtractionError."""
    storage = DocumentStorage(tmp_path)
    png_path = tmp_path / "doc_scan.png"
    png_path.write_bytes(_png_bytes())

    with patch("services.ocr._PADDLE_AVAILABLE", False):
        with pytest.raises(ExtractionError):
            extract_text("doc_scan", storage)


def test_extract_text_from_file_raises_for_image_when_paddle_unavailable(tmp_path):
    png_path = tmp_path / "scan.png"
    png_path.write_bytes(_png_bytes())

    with patch("services.ocr._PADDLE_AVAILABLE", False):
        with pytest.raises(OcrExtractionError, match="PaddleOCR"):
            extract_text_from_file(png_path)


# ---------------------------------------------------------------------------
# AI-08: mocked PaddleOCR success path for image
# ---------------------------------------------------------------------------

def test_extract_text_from_file_image_with_mocked_ocr(tmp_path):
    """Verify the OCR dispatch path returns normalised text when PaddleOCR is mocked."""
    png_path = tmp_path / "scan.png"
    png_path.write_bytes(_png_bytes())

    fake_result = [  # PaddleOCR nested structure: list-of-pages -> list-of-items
        [
            [[[0, 0], [10, 0], [10, 10], [0, 10]], ("Hello OCR World", 0.98)],
        ]
    ]

    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = fake_result

    with patch("services.ocr._PADDLE_AVAILABLE", True), \
         patch("services.ocr._ocr_instance", mock_ocr_instance):
        text = extract_text_from_file(png_path)

    assert "Hello OCR World" in text


# ---------------------------------------------------------------------------
# AI-08: scanned PDF falls back to OCR
# ---------------------------------------------------------------------------

def test_scanned_pdf_falls_back_to_ocr_when_paddle_unavailable(tmp_path):
    """A PDF that returns near-zero embedded text should trigger OCR.
    Without PaddleOCR, an ExtractionError is expected."""
    from pypdf import PdfWriter

    # Create a PDF with no embedded text (simulated scanned page)
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    blank_pdf_path = tmp_path / "doc_blank.pdf"
    with blank_pdf_path.open("wb") as f:
        writer.write(f)

    storage = DocumentStorage(tmp_path)

    with patch("services.ocr._PADDLE_AVAILABLE", False):
        with pytest.raises(ExtractionError):
            extract_text("doc_blank", storage)


# ---------------------------------------------------------------------------
# AI-08: normalisation helper
# ---------------------------------------------------------------------------

def test_normalize_collapses_whitespace():
    assert _normalize("hello   world") == "hello world"


def test_normalize_collapses_blank_lines():
    result = _normalize("line1\n\n\n\n\nline2")
    assert "\n\n\n" not in result
    assert "line1" in result
    assert "line2" in result


def test_normalize_strips_leading_trailing():
    assert _normalize("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# AI-08: unsupported type via extract_text still raises UnsupportedDocumentTypeError
# ---------------------------------------------------------------------------

def test_extract_text_unsupported_type(tmp_path):
    storage = DocumentStorage(tmp_path)
    (tmp_path / "doc_bad.docx").write_bytes(b"PK\x03\x04")
    with pytest.raises(UnsupportedDocumentTypeError):
        extract_text("doc_bad", storage)
