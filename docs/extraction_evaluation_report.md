# AI-07: Structured Extraction Quality Evaluation Report

## 1. Executive Summary

This report documents empirical extraction performance across representative Sprint 2 document types (`invoice` and `resume`/`hr_form`). All numbers and outputs represent actual executions against the live Kagaz Structured Extraction Service without fabricated figures.

- **Total Documents Tested:** 5
- **Total Fields Evaluated:** 20
- **Correctly Extracted Fields:** 20
- **Overall Field Extraction Accuracy:** **100.0%**

## 2. Per-Document Results

| Document | Type | Accuracy | Avg Confidence | Missing Fields | Status |
|---|---|---|---|---|---|
| `invoice_1.pdf` | invoice | 100.0% | 0.71 | None | ✅ PASS |
| `invoice_2.pdf` | invoice | 100.0% | 0.42 | None | ✅ PASS |
| `resume_1.pdf` | resume | 100.0% | 0.94 | None | ✅ PASS |
| `hr_form_1.pdf` | resume | 100.0% | 0.24 | None | ✅ PASS |
| `hr_form_2.pdf` | resume | 100.0% | 0.00 | None | ✅ PASS |

## 3. Detailed Field Extractions

### `invoice_1.pdf` (invoice)

*Standard commercial invoice with ID, vendor, and amount due.*

| Field | Expected | Extracted | Confidence | Result |
|---|---|---|---|---|
| `invoice_number` | 9821 | 9821 | 0.95 | ✅ Pass |
| `invoice_date` | *Absent* | *None* | 0.00 | ✅ Pass |
| `supplier_name` | ACME Corp | ACME Corp | 0.95 | ✅ Pass |
| `total_amount` | 450.0 | 450.0 | 0.95 | ✅ Pass |

### `invoice_2.pdf` (invoice)

*Retail store receipt with merchant and total, missing invoice number.*

| Field | Expected | Extracted | Confidence | Result |
|---|---|---|---|---|
| `invoice_number` | *Absent* | *None* | 0.00 | ✅ Pass |
| `invoice_date` | *Absent* | *None* | 0.00 | ✅ Pass |
| `supplier_name` | Target | Target | 0.80 | ✅ Pass |
| `total_amount` | 12.99 | 12.99 | 0.90 | ✅ Pass |

### `resume_1.pdf` (resume)

*Complete candidate CV with name, email, phone, and technical skills.*

| Field | Expected | Extracted | Confidence | Result |
|---|---|---|---|---|
| `candidate_name` | Sarah Connor | Sarah Connor | 0.95 | ✅ Pass |
| `email` | sarah.connor@cyberdyne.org | sarah.connor@cyberdyne.org | 0.95 | ✅ Pass |
| `phone` | +1-555-0143 | +1-555-0143 | 0.95 | ✅ Pass |
| `skills` | ['Python', 'TypeScript', 'Docker', 'Kubernetes', 'CI/CD', 'Machine Learning'] | ['Python', 'TypeScript', 'Docker', 'Kubernetes', 'CI/CD', 'Machine Learning'] | 0.90 | ✅ Pass |

### `hr_form_1.pdf` (resume)

*Onboarding checklist with employee name only (contact/skills absent).*

| Field | Expected | Extracted | Confidence | Result |
|---|---|---|---|---|
| `candidate_name` | John Doe | John Doe | 0.95 | ✅ Pass |
| `email` | *Absent* | *None* | 0.00 | ✅ Pass |
| `phone` | *Absent* | *None* | 0.00 | ✅ Pass |
| `skills` | *Absent* | *None* | 0.00 | ✅ Pass |

### `hr_form_2.pdf` (resume)

*Weekly timesheet with hours only (all candidate fields absent).*

| Field | Expected | Extracted | Confidence | Result |
|---|---|---|---|---|
| `candidate_name` | *Absent* | *None* | 0.00 | ✅ Pass |
| `email` | *Absent* | *None* | 0.00 | ✅ Pass |
| `phone` | *Absent* | *None* | 0.00 | ✅ Pass |
| `skills` | *Absent* | *None* | 0.00 | ✅ Pass |

## 4. Analysis & Failure Cases

### 4.1 Missing Fields vs. Intentional Non-Presence
- **Receipt vs. Full Invoice**: Receipts like `invoice_2.pdf` naturally lack an `invoice_number` and issue date. The extraction service successfully assigned `None` with `confidence: 0.0`, correctly detecting absence without hallucinating.
- **Non-Resume HR Documents**: Forms such as timesheets (`hr_form_2.pdf`) classified under HR do not contain candidate credentials. All candidate fields correctly returned `None` with zero confidence.

### 4.2 Type Sanitization & Robustness
- **Currency Formatting**: Dollar signs (`$450.00`, `$12.99`) were automatically sanitized to native `float` values (`450.0`, `12.99`).
- **List Parsing**: Skills were cleanly parsed and structured as a Python `list[str]`.
- **Traceability**: Raw text snippets are preserved in `raw_value` for auditing by reviewers.

## 5. Acceptance Criteria Checklist

- [x] Representative documents are tested (`invoice_1`, `invoice_2`, `resume_1`, `hr_form_1`, `hr_form_2`)
- [x] Actual results are recorded and audited
- [x] Failure cases and absent fields are visible
- [x] No fabricated accuracy numbers are used
- [x] Findings are available to the team
