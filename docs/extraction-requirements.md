# REQ-08: Extraction Requirements & Acceptance Criteria Specification

## 1. Objective & Scope

This document specifies the functional requirements, field expectations, per-field confidence scoring rules, tenant isolation constraints, and testable acceptance criteria for **Kagaz Sprint 2 Structured Extraction**.

It provides complete traceability to:
- **FR-09:** Key-Field Extraction
- **FR-10:** Extracted Information Review and Correction
- **US-04:** Role-Based Access & Tenant Isolation
- **US-14:** Key-Field Extraction
- **US-15:** Reviewer Correction of Extracted Fields
- **NFR-AI-01:** AI Confidence Thresholds and Traceability

---

## 2. Agreed Initial Document Types

To ensure high quality, reliability, and testability, Sprint 2 establishes a focused representative set across the 4 classification domains (`academics`, `hr_documents`, `financial`, `general_confidential`):

| Document Type | Target Domain | Pipeline Category | Primary Business Value |
|---|---|---|---|
| **`invoice`** | Financial | `DocumentCategory.FINANCIAL` | Automated invoice indexing, payable validation, supplier record lookup. |
| **`resume`** (aliased to `hr_documents`) | HR Documents | `DocumentCategory.HR_DOCUMENTS` | Candidate intake, credential verification, skill matching. |

---

## 3. Required Fields & Value Expectations

### 3.1 Invoice Extraction Specification (`InvoiceExtraction`)

| Field Name | Type | Presence | Expected Format / Constraints | Edge Case Handling |
|---|---|---|---|---|
| `invoice_number` | `str` | Optional / Recommended | Alphanumeric identifier, e.g. `"INV-2024-9821"` or `"9821"`. | If document is a retail receipt without an invoice ID, returned as `null` with `confidence: 0.0`. |
| `invoice_date` | `str` | Optional / Recommended | Standardized date string (`YYYY-MM-DD` preferred), or verbatim document date snippet. | If missing from text, returned as `null` with `confidence: 0.0`. |
| `supplier_name` | `str` | Required if present | Name of issuing company, merchant, or organization. | If vendor name is ambiguous, model extracts primary header text and provides evidence snippet. |
| `total_amount` | `float` | Required if present | Positive numeric value representing monetary balance payable (e.g. `450.00`). | Currency symbols (`$`, `€`, `£`) and thousand separators (`,`/`.`) are automatically stripped and sanitized. |

### 3.2 Resume / HR Form Extraction Specification (`ResumeExtraction`)

| Field Name | Type | Presence | Expected Format / Constraints | Edge Case Handling |
|---|---|---|---|---|
| `candidate_name` | `str` | Required if present | Full name of the applicant / employee (e.g. `"Sarah Connor"`). | Extracted from header or title block. `null` on generic forms like blank timesheets. |
| `email` | `str` | Optional / Recommended | Valid email format (`username@domain.tld`). | If unextractable or absent, returned as `null` with `confidence: 0.0`. |
| `phone` | `str` | Optional / Recommended | Telephone / mobile number string, preserving country and area code. | Strips non-dialable annotations. `null` if absent. |
| `skills` | `List[str]` | Optional / Recommended | Clean list of individual technical or professional skills. | Comma-separated strings, bullets, or pipe delimiters are automatically split into distinct string tokens. |

---

## 4. Per-Field Confidence Standard

Each field in an extraction response is encapsulated within an `ExtractedField[T]` structure:

```json
{
  "value": "INV-2024-9821",
  "confidence": 0.95,
  "raw_value": "Invoice #INV-2024-9821",
  "is_present": true
}
```

### 4.1 Confidence Scale & Semantics
- **Range:** Floating-point number between `0.0` (completely absent / unidentifiable) and `1.0` (highest confidence).
- **Present Field:** `confidence >= 0.0` reflecting AI extraction certainty; `is_present = true`.
- **Absent Field:** `value = null`, `confidence = 0.0`, `raw_value = null`, `is_present = false`.

### 4.2 Review Thresholds (NFR-AI-01 & FR-10)
- **High Confidence ($\ge 0.85$):** Passed downstream to policy validation and automated workflows.
- **Low / Medium Confidence ($< 0.85$):** Flagged in the Reviewer UI for human inspection and one-click correction.
- **Auditable Evidence:** The `raw_value` attribute preserves the unparsed text excerpt from the document, allowing reviewers to verify the source without re-reading the entire page.

---

## 5. Frontend & Backend Contract Alignment

To prevent field mismatch across the Kagaz stack:
1. **Naming:** All field names use lowercase **`snake_case`** matching across Python Pydantic models, JSON API responses, and TypeScript interfaces:
   - Invoice: `invoice_number`, `invoice_date`, `supplier_name`, `total_amount`
   - Resume: `candidate_name`, `email`, `phone`, `skills`
2. **Standard Serialization:**
   - Detailed payload: returns full `ExtractedField` objects with `confidence` and `raw_value` for the Reviewer interface.
   - Flat payload: `to_flat_dict()` provides direct key-value mapping for simple consumers.

---

## 6. Acceptance Criteria

### 6.1 Tenant Isolation & Role-Based Access for Extraction (US-04)
- **AC-US04-1 (Multi-Tenant Scoping):** Extracted field records are strictly scoped by `organization_id`. An organization's extracted data is never retrievable or editable by users belonging to another organization.
- **AC-US04-2 (Role Permissions):**
  - `SUBMITTER`: Can upload documents and view extraction status.
  - `REVIEWER`: Authorized within the organization to inspect extracted fields, view confidence flags, and save manual corrections.
  - `APPROVER`: Authorized to review verified extracted data during final decision-making.
- **AC-US04-3 (Authentication Enforcement):** Unauthenticated API requests attempting to access or modify extracted data are rejected with HTTP 401.

### 6.2 Key-Field Extraction (US-14)
- **AC-US14-1 (Pipeline Sequencing):** Field extraction occurs strictly **after** document classification has resolved the document category.
- **AC-US14-2 (Type-Specific Schemas):** Invoices return invoice-specific fields; Resumes return candidate contact and qualification fields.
- **AC-US14-3 (Missing Field Consistency):** Missing fields in a document return `null` with `confidence: 0.0` rather than causing extraction failures or hallucinating fabricated values.
- **AC-US14-4 (Type Safety & Coercion):** Numeric fields (e.g. `total_amount`) are guaranteed floats; list fields (e.g. `skills`) are guaranteed lists of non-empty strings.
- **AC-US14-5 (Independent Testability):** The extraction service is decoupled from the web/API layer and executes deterministically with mockable transports in unit tests.

---

## 7. Traceability Matrix

| Requirement | User Story | Implementation Component | Test Suite |
|---|---|---|---|
| FR-09 Key-Field Extraction | US-14 | `app.schemas.extraction`, `services.structured_extraction` | `test_extraction_schemas.py`, `test_structured_extraction.py` |
| FR-10 Field Review & Correction | US-15 | `ExtractedField.raw_value`, `api.documents.correct_classification` | `test_extraction_schemas.py` |
| FR-03 Role-Based Access | US-04 | `api.auth.require_submitter`, `app.crud.document` | `test_document_metadata.py`, `test_upload.py` |
| NFR-AI-01 Per-field Confidence | US-14, US-15 | `ExtractedField.confidence` | `test_extraction_schemas.py`, `evaluate_extraction.py` |
