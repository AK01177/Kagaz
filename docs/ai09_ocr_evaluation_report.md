# AI-09: OCR Evaluation Report

**Issue**: #81 · AI-09 — OCR Evaluation  
**Sprint**: 2  
**Prepared by**: AI/Backend Team  
**Date**: 2026-10-26  

---

## 1. Objective

Verify OCR and text extraction quality across all supported file types introduced in AI-08:
- Text-based PDF
- Scanned (image-only) PDF
- PNG image
- JPG / JPEG image
- Low-quality or unreadable sample

---

## 2. Test Environment

| Component | Detail |
|---|---|
| OCR Engine | PaddleOCR (optional; mocked in CI) |
| PDF text extraction | pypdf |
| PDF rendering | pdf2image + poppler |
| Test runner | pytest |
| Platform | Windows / Linux |

> **Note**: PaddleOCR and pdf2image are **optional dependencies** and are not installed in the current development environment. Live OCR tests were verified using mock stubs in the automated test suite (`tests/test_ai08_ocr_extraction.py`). When the team provisions an environment with these packages installed, the live samples below should be re-run.

---

## 3. Test Samples

| # | File Type | Sample | Expected text snippet | Status |
|---|---|---|---|---|
| 1 | Text-based PDF | `sample/invoice_sample.pdf` | "Invoice", "Total", "Supplier" | ✅ Pass (pypdf) |
| 2 | Scanned PDF | `sample/scanned_receipt.pdf` | "Receipt", "Amount" | ⏳ Pending (PaddleOCR not installed) |
| 3 | PNG image | `sample/form_scan.png` | "Name", "Date" | ⏳ Pending (PaddleOCR not installed) |
| 4 | JPG image | `sample/id_card.jpg` | "ID", "Number" | ⏳ Pending (PaddleOCR not installed) |
| 5 | JPEG image | `sample/handwritten_note.jpeg` | Partial text | ⏳ Pending (PaddleOCR not installed) |
| 6 | Low-quality / unreadable | `sample/corrupt_scan.pdf` | (none) | ✅ Graceful failure (OcrExtractionError) |

---

## 4. Automated Test Coverage

The following automated tests (all passing in CI) cover the AI-08/09 scope:

| Test | File | Result |
|---|---|---|
| `test_extract_text_reads_text_based_pdf` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_extract_text_raises_for_image_when_paddle_unavailable` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_extract_text_from_file_raises_for_image_when_paddle_unavailable` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_extract_text_from_file_image_with_mocked_ocr` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_scanned_pdf_falls_back_to_ocr_when_paddle_unavailable` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_normalize_collapses_whitespace` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_normalize_collapses_blank_lines` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_normalize_strips_leading_trailing` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_unsupported_type_rejected` | `test_ai08_ocr_extraction.py` | ✅ Pass |
| `test_supported_extensions_include_images` | `test_ai08_ocr_extraction.py` | ✅ Pass |

---

## 5. Observed Failure Cases

| Scenario | Behaviour | Expected |
|---|---|---|
| PaddleOCR not installed, image uploaded | `OcrExtractionError` raised | ✅ Graceful |
| Blank / scanned PDF without OCR libs | `ExtractionError` raised | ✅ Graceful |
| Unsupported extension (.docx) | `UnsupportedFormatError` raised | ✅ Graceful |
| File with valid extension but corrupt content | `OcrExtractionError` or `ExtractionError` | ✅ Graceful |
| Empty file uploaded | `UploadError(400, INVALID_FILE)` before OCR | ✅ Graceful |

---

## 6. OCR Output Quality (Mocked)

Because PaddleOCR was not available in this environment, OCR output quality was assessed using the mocked stub test:

```
Input:  1×1 PNG (minimal valid PNG)
Mock OCR result:  "Hello OCR World" (confidence 0.98)
Normalised output: "Hello OCR World"
Result: Text returned correctly, whitespace normalised
```

**No accuracy claims are made** about the live PaddleOCR output quality without running it against real documents.

---

## 7. Implementation Notes

- **Text-based PDFs** use the existing pypdf path (fast, reliable, no external deps).
- **Scanned PDFs** are detected by absence of embedded text and routed to `_ocr_pdf()`.
- **Images** always go through `_extract_via_ocr_from_image()`.
- **OCR provider (PaddleOCR) is fully encapsulated** behind `services/ocr.py`. The classification and extraction services call `services.extraction.extract_text()` unchanged; they never import PaddleOCR directly.
- **Unreadable documents** produce a controlled `OcrExtractionError` or `ExtractionError`, which upstream code catches and converts to an HTTP 422 or document `FAILED` status.

---

## 8. Remaining Work (Follow-up)

- [ ] Install PaddleOCR + pdf2image in the dev environment and run against real samples listed in Section 3.
- [ ] Record actual OCR output and confidence scores for each sample.
- [ ] Evaluate quality on low-quality images (blurry, handwritten) and document accuracy without inventing results.
- [ ] Add `sample/` files for scanned PDF, PNG, JPG, JPEG test cases.

---

## 9. Acceptance Criteria Status

| Criterion | Status |
|---|---|
| Every supported file type has at least one test sample | ✅ (automated mocks; live samples pending install) |
| Results and failure cases are documented | ✅ (this document) |
| OCR output checked for missing or corrupted text | ✅ (mocked path; live pending) |
| No accuracy claims are invented | ✅ |
| Unreadable documents fail gracefully | ✅ |
