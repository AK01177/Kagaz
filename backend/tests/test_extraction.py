import pytest
from reportlab.pdfgen import canvas

from services.extraction import extract_text, UnsupportedDocumentTypeError, ExtractionError
from storage.document_storage import DocumentStorage, DocumentNotFoundError


def _write_pdf(path, pages_lines):
    c = canvas.Canvas(str(path))
    for lines in pages_lines:
        y = 800
        for line in lines:
            c.drawString(72, y, line)
            y -= 20
        c.showPage()
    c.save()


@pytest.fixture
def storage(tmp_path):
    return DocumentStorage(base_dir=tmp_path)


def test_extracts_non_empty_text_for_readable_document(tmp_path, storage):
    _write_pdf(tmp_path / "doc_001.pdf", [["Hello world"]])

    text = extract_text("doc_001", storage=storage)

    assert text
    assert "Hello world" in text


def test_combines_text_from_multiple_pages_in_order(tmp_path, storage):
    _write_pdf(tmp_path / "doc_002.pdf", [["First page content"], ["Second page content"]])

    text = extract_text("doc_002", storage=storage)

    assert text.index("First page content") < text.index("Second page content")


def test_normalizes_obvious_whitespace(tmp_path, storage):
    _write_pdf(tmp_path / "doc_003.pdf", [["Spaced   out   text"]])

    text = extract_text("doc_003", storage=storage)

    assert "   " not in text
    assert text == text.strip()


def test_missing_document_raises_controlled_error(storage):
    with pytest.raises(DocumentNotFoundError):
        extract_text("does_not_exist", storage=storage)


def test_unsupported_file_type_raises_controlled_error(tmp_path, storage):
    (tmp_path / "doc_004.txt").write_text("plain text file")

    with pytest.raises(UnsupportedDocumentTypeError):
        extract_text("doc_004", storage=storage)


def test_unreadable_document_raises_controlled_error(tmp_path, storage):
    (tmp_path / "doc_005.pdf").write_bytes(b"not a real pdf")

    with pytest.raises(ExtractionError):
        extract_text("doc_005", storage=storage)
