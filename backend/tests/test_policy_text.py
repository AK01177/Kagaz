"""Reading policy files: PDF, DOCX and TXT (RAG Phase 2)."""
import io

import pytest
from docx import Document as WordDocument
from reportlab.pdfgen import canvas

from services import policy_text
from services.policy_text import (
    PolicyFileError,
    PolicyTextError,
    SourcePage,
    extract_policy_pages,
    validate_policy_file,
)


def write(tmp_path, name, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def pdf_bytes(*page_texts: str) -> bytes:
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    for text in page_texts:
        if text:
            pdf.drawString(72, 750, text)
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def docx_bytes() -> bytes:
    document = WordDocument()
    document.add_heading("Leave Policy", level=1)
    document.add_paragraph("Employees may carry over 5 days.")
    table = document.add_table(rows=2, cols=2)
    for row, values in enumerate([("Type", "Days"), ("Casual", "12")]):
        for column, value in enumerate(values):
            table.cell(row, column).text = value
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def test_pdf_pages_keep_their_numbers(tmp_path):
    pages = extract_policy_pages(write(tmp_path, "p.pdf", pdf_bytes("First page text", "Second page text")))
    assert [(p.number, p.text) for p in pages] == [(1, "First page text"), (2, "Second page text")]


def test_docx_headings_become_markdown_markers_and_tables_become_rows(tmp_path):
    (page,) = extract_policy_pages(write(tmp_path, "p.docx", docx_bytes()))
    assert page.number is None
    assert "# Leave Policy" in page.text
    assert "Employees may carry over 5 days." in page.text
    assert "Type | Days" in page.text and "Casual | 12" in page.text


def test_txt_decodes_utf8_with_bom_and_falls_back_to_windows_1252(tmp_path):
    utf8 = extract_policy_pages(write(tmp_path, "a.txt", "﻿Rupee ₹ policy".encode("utf-8")))
    legacy = extract_policy_pages(write(tmp_path, "b.txt", "caf\xe9 rule".encode("cp1252")))
    assert utf8[0].text == "Rupee ₹ policy"
    assert legacy[0].text == "café rule"


def test_a_file_with_no_text_returns_no_pages(tmp_path):
    assert extract_policy_pages(write(tmp_path, "empty.txt", b"  \n \n")) == []


def test_image_only_pdf_falls_back_to_ocr(tmp_path, monkeypatch):
    monkeypatch.setattr("services.ocr.extract_text_from_file", lambda path: "Scanned policy clause")
    pages = extract_policy_pages(write(tmp_path, "scan.pdf", pdf_bytes("")))
    assert pages == [SourcePage(None, "Scanned policy clause")]


def test_unreadable_file_raises_a_safe_error(tmp_path):
    with pytest.raises(PolicyTextError):
        extract_policy_pages(write(tmp_path, "bad.docx", b"not a zip"))


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("fake.pdf", b"hello"),
        ("empty.pdf", b""),
        ("fake.docx", b"hello"),
        ("zip.docx", b"PK\x03\x04 not really a docx"),
        ("binary.txt", b"abc\x00def"),
        ("tool.exe", b"MZ"),
    ],
)
def test_files_that_are_not_what_their_extension_claims_are_rejected(tmp_path, name, data):
    path = write(tmp_path, name, data)
    with pytest.raises(PolicyFileError):
        validate_policy_file(path, path.suffix)


@pytest.mark.parametrize(
    ("name", "make_bytes"),
    [
        ("ok.pdf", lambda: pdf_bytes("hello")),
        ("ok.docx", docx_bytes),
        ("ok.txt", lambda: b"plain policy text"),
    ],
    ids=["pdf", "docx", "txt"],
)
def test_valid_files_pass_validation(tmp_path, name, make_bytes):
    path = write(tmp_path, name, make_bytes())
    validate_policy_file(path, path.suffix)


def test_supported_formats_are_exactly_pdf_docx_txt():
    assert set(policy_text.SUPPORTED_POLICY_FORMATS) == {".pdf", ".docx", ".txt"}
