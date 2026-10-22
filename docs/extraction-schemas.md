# AI-05: Extraction Schemas & Field Definitions

## Overview

This document specifies the structured extraction schemas for **Kagaz Sprint 2**. Document information extraction is the pipeline stage following document classification: once a document's category is identified (e.g. `invoice` or `resume` / `hr_form`), Kagaz extracts a predefined set of key fields needed for downstream validation, compliance checking, and human review.

---

## 1. Initial Document Types

For Sprint 2, structured extraction targets two primary document types across the 4 core domains (`academics`, `hr_documents`, `financial`, `general_confidential`):

| Document Type Identifier | Display Name | Canonical Category | Description |
|--------------------------|--------------|--------------------|-------------|
| `invoice` / `financial` | Invoice / Financial | `DocumentCategory.FINANCIAL` | Commercial invoices, vendor bills, receipts, and financial statements. |
| `resume` / `hr_documents` | Resume / HR Document | `DocumentCategory.HR_DOCUMENTS` | Resumes, curricula vitae, and onboarding qualification records. |

---

## 2. Field Structure & Confidence Standard

Every extracted field follows the standardized `ExtractedField[T]` model:

```json
{
  "value": "<typed value or null>",
  "confidence": 0.95,
  "raw_value": "<original text snippet from document>",
  "is_present": true
}
```

### Attributes:
- **`value`** (`Optional[T]`): The parsed, type-validated data item (e.g., `float` for amount, `List[str]` for skills). Set to `null` if the field was not detected.
- **`confidence`** (`float`, range `0.0` - `1.0`): The model's confidence in the extracted value.
- **`raw_value`** (`Optional[str]`): The unparsed text snippet from the document, providing auditable evidence for the reviewer.
- **`is_present`** (`bool`): Flag indicating if the field was detected in the document text. Automatically `false` if `value` is `null`.

### Missing Field Representation:
When a field is not present in the document:
```json
{
  "value": null,
  "confidence": 0.0,
  "raw_value": null,
  "is_present": false
}
```

---

## 3. Schema Specifications

### 3.1 Invoice Schema (`InvoiceExtraction`)

| Field Name | Type | Description | Example |
|------------|------|-------------|---------|
| `invoice_number` | `str` | Unique reference or billing number of the invoice. | `"INV-2024-9821"` |
| `invoice_date` | `str` | Date invoice was issued (standardized to `YYYY-MM-DD` when possible). | `"2024-10-15"` |
| `supplier_name` | `str` | Name of the issuing merchant, contractor, or vendor. | `"ACME Corporation"` |
| `total_amount` | `float` | Net or gross monetary balance payable on the invoice. | `450.00` |

### 3.2 Resume Schema (`ResumeExtraction`)

| Field Name | Type | Description | Example |
|------------|------|-------------|---------|
| `candidate_name` | `str` | Full name of the job applicant or employee. | `"Jane Doe"` |
| `email` | `str` | Primary email address of the applicant. | `"jane.doe@example.com"` |
| `phone` | `str` | Contact phone / mobile number. | `"+1-555-0149"` |
| `skills` | `List[str]` | List of identified technical, domain, or soft skills. | `["Python", "FastAPI", "React", "SQL"]` |

---

## 4. Frontend & Backend Contract Alignment

To prevent field mismatch between backend extraction and frontend display/editing:
- All schema keys use **snake_case** matching backend attribute names (`invoice_number`, `invoice_date`, `supplier_name`, `total_amount`, `candidate_name`, `email`, `phone`, `skills`).
- Schema definitions can be inspected dynamically via `get_field_definitions(doc_type)`.
- Flat dictionary conversion is supported via `to_flat_dict()` for straightforward JSON payload responses.

---

## 5. Schema Registry & Extensibility

Schemas are registered in `backend/app/schemas/extraction.py`:

```python
from app.schemas.extraction import (
    get_extraction_schema,
    get_field_definitions,
    get_supported_extraction_types,
)

# Look up schema class dynamically
schema_cls = get_extraction_schema("invoice")

# Inspect field definitions for prompts or UI
fields = get_field_definitions("invoice")
```

To add a new document type in future sprints:
1. Subclass `BaseDocumentExtraction`.
2. Define fields with `ExtractedField[T]` annotations.
3. Register the class in `EXTRACTION_SCHEMA_REGISTRY`.
