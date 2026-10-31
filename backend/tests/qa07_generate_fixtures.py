"""Create synthetic QA-07 fixtures. Run from backend: python tests/qa07_generate_fixtures.py."""
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parent / "fixtures" / "qa07"
LINES = ["INVOICE", "Invoice Number: INV-007", "Supplier: Test Company", "Total: 1250"]
TEXT = "\n".join(LINES)


def generate():
    ROOT.mkdir(parents=True, exist_ok=True)
    font = None
    for name in ["C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"]:
        try:
            font = ImageFont.truetype(name, 46)
            break
        except OSError:
            pass
    font = font or ImageFont.load_default(size=46)
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(LINES):
        draw.text((100, 100 + i * 150), line, fill="black", font=font)
    image.save(ROOT / "invoice.png")
    for extension in ["jpg", "jpeg"]:
        image.save(ROOT / f"invoice.{extension}", format="JPEG", quality=95)
    Image.new("RGB", (1600, 1000), "white").save(ROOT / "blank.png")

    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(600, 750), invariant=1)
    pdf.setFont("Helvetica", 22)
    for i, line in enumerate(LINES):
        pdf.drawString(50, 650 - i * 70, line)
    pdf.save()
    (ROOT / "invoice.pdf").write_bytes(stream.getvalue())
    pdf = canvas.Canvas(str(ROOT / "scanned.pdf"), pagesize=(600, 750), invariant=1)
    pdf.drawImage(ImageReader(image), 0, 187.5, width=600, height=375)
    pdf.save()

    (ROOT / "note.txt").write_text(TEXT, encoding="utf-8")
    (ROOT / "empty.pdf").write_bytes(b"")
    (ROOT / "broken.pdf").write_bytes(b"%PDF-1.4\nnot a readable PDF")
    (ROOT / "broken.png").write_bytes(b"not an image")
    (ROOT / "broken.jpg").write_bytes(b"not an image")
    # These retain a valid signature but cannot actually be decoded.
    (ROOT / "truncated.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    (ROOT / "truncated.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)

    original = (ROOT / "invoice.pdf").read_bytes()
    header, rest = original.split(b"\n", 1)
    target = 10 * 1024 * 1024 + 1
    padding = target - len(original) - 2
    oversized = header + b"\n%" + b" " * padding + b"\n" + rest
    (ROOT / "oversized.pdf").write_bytes(oversized)
    assert len(oversized) == target
    (ROOT / "expected.json").write_text(json.dumps({
        "text": TEXT, "invoice_number": "INV-007",
        "supplier_name": "Test Company", "total_amount": 1250,
        "oversized_bytes": target,
    }, indent=2), encoding="utf-8")
    assert "INV-007" in PdfReader(ROOT / "invoice.pdf").pages[0].extract_text()
    scanned = PdfReader(ROOT / "scanned.pdf")
    assert not (scanned.pages[0].extract_text() or "").strip()
    assert len(scanned.pages[0].images) == 1
    for name in ["invoice.png", "invoice.jpg", "invoice.jpeg", "blank.png"]:
        with Image.open(ROOT / name) as img:
            img.verify()
    print(f"Created and validated QA-07 fixtures in {ROOT}")


if __name__ == "__main__":
    generate()
