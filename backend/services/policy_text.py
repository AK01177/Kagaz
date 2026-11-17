"""Read policy source files (PDF, DOCX, TXT) into plain text pages for chunking.

Page numbers are kept for PDFs so citations can point at a page. DOCX and TXT have no
fixed pages, so they come back as one page without a number. DOCX headings are written
as Markdown-style `## Heading` lines, the same marker the chunker understands in TXT.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

SUPPORTED_POLICY_FORMATS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}
SUPPORTED_POLICY_EXTENSIONS = ", ".join(sorted(SUPPORTED_POLICY_FORMATS))

_DOCX_HEADING_STYLE = re.compile(r"^Heading\s*(\d)$", re.IGNORECASE)
_HORIZONTAL_SPACE = re.compile(r"[ \t ]+")


class PolicyFileError(Exception):
    """The uploaded policy file is unreadable or not what its extension claims."""


class PolicyTextError(Exception):
    """Text could not be extracted from a stored policy file."""


@dataclass(frozen=True)
class SourcePage:
    number: int | None  # 1-based page number; None when the format has no fixed pages
    text: str


def validate_policy_file(path: Path, extension: str) -> None:
    """Check the file really is the claimed format before it is stored or processed."""
    try:
        if extension == ".pdf":
            _validate_pdf(path)
        elif extension == ".docx":
            _validate_docx(path)
        elif extension == ".txt":
            _decode_text(path.read_bytes())
        else:
            raise PolicyFileError(f"Policy files must be one of: {SUPPORTED_POLICY_EXTENSIONS}.")
    except PolicyFileError:
        raise
    except Exception as exc:  # corrupt files raise many different library errors
        raise PolicyFileError(f"The {extension[1:].upper()} file is unreadable or corrupt.") from exc


def extract_policy_pages(path: Path) -> list[SourcePage]:
    """Return the file's text, page by page. Raises PolicyTextError when nothing is readable."""
    extension = path.suffix.lower()
    try:
        if extension == ".pdf":
            pages = _read_pdf(path)
        elif extension == ".docx":
            pages = [SourcePage(None, _read_docx(path))]
        elif extension == ".txt":
            pages = [SourcePage(None, _decode_text(path.read_bytes()))]
        else:
            raise PolicyTextError(f"Unsupported policy format: {extension}")
    except PolicyTextError:
        raise
    except Exception as exc:
        raise PolicyTextError("Policy text extraction failed.") from exc
    pages = [SourcePage(page.number, _clean(page.text)) for page in pages]
    return [page for page in pages if page.text]


def _validate_pdf(path: Path) -> None:
    with path.open("rb") as source:
        if source.read(5) != b"%PDF-":
            raise PolicyFileError("The file is not a PDF.")
        source.seek(0)
        reader = PdfReader(source)
        if reader.is_encrypted or len(reader.pages) == 0:
            raise PolicyFileError("Provide an unencrypted PDF with at least one page.")


def _validate_docx(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise PolicyFileError("The file is not a DOCX document.")
    _open_docx(path)  # raises if the package is not a valid Word document


def _decode_text(data: bytes) -> str:
    if b"\x00" in data:
        raise PolicyFileError("The text file contains binary data.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise PolicyFileError("The text file uses an unsupported encoding.")


def _read_pdf(path: Path) -> list[SourcePage]:
    reader = PdfReader(str(path))
    pages = [SourcePage(number, page.extract_text() or "") for number, page in enumerate(reader.pages, start=1)]
    if any(_clean(page.text) for page in pages):
        return pages
    # Image-only PDF: fall back to OCR, which cannot tell us page boundaries.
    from services.ocr import extract_text_from_file  # imported lazily: heavy optional dependency

    return [SourcePage(None, extract_text_from_file(path))]


def _open_docx(path: Path):
    from docx import Document as open_docx  # python-docx

    return open_docx(str(path))


def _read_docx(path: Path) -> str:
    """Body text in document order: headings, paragraphs, and table rows as `a | b | c`."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = _open_docx(path)
    lines: list[str] = []
    for element in document.element.body.iterchildren():
        if element.tag.endswith("}p"):
            paragraph = Paragraph(element, document)
            text = paragraph.text.strip()
            if not text:
                lines.append("")
                continue
            level = _heading_level(paragraph.style.name if paragraph.style is not None else "")
            lines.append(f"{'#' * level} {text}" if level else text)
        elif element.tag.endswith("}tbl"):
            lines.append("")
            for row in Table(element, document).rows:
                cells = list(dict.fromkeys(cell.text.strip() for cell in row.cells))  # merged cells repeat
                row_text = " | ".join(cell for cell in cells if cell)
                if row_text:
                    lines.append(row_text)
            lines.append("")
    return "\n".join(lines)


def _heading_level(style_name: str) -> int:
    if style_name.strip().lower() == "title":
        return 1
    match = _DOCX_HEADING_STYLE.match(style_name.strip())
    return min(int(match.group(1)), 6) if match else 0


def _clean(text: str) -> str:
    """Normalise newlines and spaces while keeping line structure (the chunker relies on it)."""
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [_HORIZONTAL_SPACE.sub(" ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
