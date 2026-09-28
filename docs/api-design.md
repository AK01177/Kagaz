# Kagaz — API Design

## 1. Purpose

This document defines the initial API contract between the **Next.js frontend** and **FastAPI backend**.

The goal is simple: both sides should know **which endpoint to call, what to send, and what comes back**.

### Main workflow

```text
Upload
  ↓
Extract / OCR
  ↓
Classify
  ↓
Extract Fields
  ↓
Validate with Policy
  ↓
Detect Issues
  ↓
Route
  ↓
Review / Approve
  ↓
Audit
```

### Sprint 1 scope

```text
Upload → Classify
```

The later endpoints are documented here so the team has a common direction, but they are implemented in later sprints.

---

## 2. Common API Rules

### Base URL

```text
/api
```

Example:

```http
POST /api/documents
```

### Request / response format

- JSON for normal requests and responses
- `multipart/form-data` for document upload
- `snake_case` for JSON fields
- IDs are treated as opaque strings
- Timestamps use ISO 8601

### Authentication

Kagaz uses **JWT + RBAC**.

Protected requests use:

```http
Authorization: Bearer <access_token>
```

The backend checks:

```text
JWT valid?
   ↓
User active?
   ↓
Correct role?
   ↓
Correct organization?
   ↓
Allow / deny
```

### Organization isolation

Users must only access data belonging to organizations they are authorized to access.
The backend should determine organization scope from the authenticated user rather than trusting arbitrary organization IDs sent by the frontend.

### Roles

Core roles:

```text
SUBMITTER
REVIEWER
APPROVER
ORG_ADMIN
SYSTEM_ADMIN
COMPLIANCE
AUDITOR
```

Not every role needs a separate UI in the first release.

---

# 3. API Overview

| Method | Endpoint | Purpose | Status |
|---|---|---|---|
| GET | `/api/health` | Check backend | Current |
| POST | `/api/auth/login` | Login | Current/foundation |
| POST | `/api/documents` | Upload document | Sprint 1 |
| GET | `/api/documents/{document_id}` | Get document | Sprint 1 |
| POST | `/api/documents/{document_id}/classify` | Classify document | Sprint 1 |
| GET | `/api/documents/{document_id}/extract` | Get extracted fields | Later |
| GET | `/api/documents/{document_id}/validate` | Get validation result | Later |
| POST | `/api/documents/{document_id}/approve` | Approve document | Later |
| POST | `/api/documents/{document_id}/reject` | Reject document | Later |
| GET | `/api/policies` | List policies | Later |
| POST | `/api/policies` | Add policy | Later |
| POST | `/api/chatbot/query` | Ask chatbot | Later |
| GET | `/api/audit/{document_id}` | Get audit trail | Later |
| GET | `/api/admin/users` | Manage users | Later |
| PUT | `/api/admin/users/{user_id}` | Update user/role | Later |
| POST | `/api/policies/{policy_id}/backtest` | Policy backtest | Future |

---

# 4. Standard Error Format

All API errors should use the same basic structure:

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document does not exist."
  }
}
```

Common status codes:

| Code | Meaning |
|---|---|
| `400` | Bad request |
| `401` | Missing/invalid authentication |
| `403` | Authenticated but not allowed |
| `404` | Resource not found |
| `409` | Invalid current state / conflict |
| `413` | File too large |
| `415` | Unsupported file type |
| `422` | Validation/model output error |
| `500` | Internal server error |
| `503` | Temporary external/AI service failure |

---

# 5. Current Sprint 1 Endpoints

## 5.1 Health Check

### `GET /api/health`

No authentication.

Response:

```json
{
  "status": "ok"
}
```

---

## 5.2 Login

### `POST /api/auth/login`

No authentication.

Request:

```json
{
  "email": "user@example.com",
  "password": "password"
}
```

Response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "user_id": "usr_001",
    "name": "Example User",
    "email": "user@example.com",
    "role": "SUBMITTER",
    "organization_id": "org_001"
  }
}
```

Errors:

```text
400 malformed request
401 invalid credentials
403 account disabled / not allowed
```

---

## 5.3 Upload Document

Implementation note (BE-02): the current endpoint accepts unencrypted PDF files
up to 10 MiB and persists files plus JSON metadata locally. DOCX/image support and
database integration remain pending. JWT validation is implemented for active
`SUBMITTER` tokens; login/token issuance and live user-status lookup remain pending.
See `backend/README.md` for required claims and local testing instructions.

The multipart request body is capped during receipt at 10 MiB plus 64 KiB of
multipart overhead, with HTTP 413 for oversized requests. The file itself is
still limited to 10 MiB. The request cap also applies without Content-Length.

### `POST /api/documents`

Authentication: **Required**

Typical role: `SUBMITTER`

Content type:

```text
multipart/form-data
```

Request:

```text
file = invoice.pdf
```

Response `201 Created`:

```json
{
  "document_id": "doc_001",
  "filename": "invoice.pdf",
  "file_type": "application/pdf",
  "status": "UPLOADED",
  "uploaded_at": "2026-09-23T17:30:00Z"
}
```

Errors:

```text
400 invalid / empty file
401 not authenticated
403 upload not allowed
413 file too large
415 unsupported file type
500 storage failure
```

Important: upload should return the document ID without waiting for the whole AI pipeline.

---

## 5.4 Get Document

### `GET /api/documents/{document_id}`

Authentication: **Required**

Purpose: frontend uses this to read the current document state.

Response after upload:

```json
{
  "document_id": "doc_001",
  "filename": "invoice.pdf",
  "status": "UPLOADED",
  "category": null,
  "confidence": null
}
```

Response after classification:

```json
{
  "document_id": "doc_001",
  "filename": "invoice.pdf",
  "status": "CLASSIFIED",
  "category": "Invoice",
  "confidence": 0.91
}
```

Errors:

```text
401 unauthenticated
403 not allowed to access document
404 document not found
```

Frontend rule: **do not guess the document status. Use the backend value.**

---

## 5.5 Classify Document

### `POST /api/documents/{document_id}/classify`

Authentication: **Required**

Request body: none.

Example:

```http
POST /api/documents/doc_001/classify
Authorization: Bearer <jwt>
```

Response:

```json
{
  "document_id": "doc_001",
  "category": "Invoice",
  "confidence": 0.91,
  "status": "CLASSIFIED"
}
```

### Backend flow

```text
Document ID
   ↓
Find document
   ↓
Check access
   ↓
Load file
   ↓
Extract text
   ↓
Run classifier
   ↓
Validate result
   ↓
Save result
   ↓
Return response
```

### Classification rules

- `category` must be one of Kagaz's supported document types.
- `confidence` is a number from `0` to `1`.
- Backend validates the AI result before returning it.
- Frontend does not depend on the AI provider.
- Jev may be used for classification, but it is an internal implementation detail.

Errors:

```text
401 unauthenticated
403 not allowed
404 document not found
409 document not ready / invalid state
422 invalid classifier output
500 processing failure
503 AI service unavailable
```

---

# 6. Planned Workflow Endpoints

These follow the same contract style and will be implemented in later sprints.

## Extract Fields

### `GET /api/documents/{document_id}/extract`

Returns structured fields and confidence.

Example:

```json
{
  "document_id": "doc_001",
  "document_type": "Invoice",
  "fields": {
    "invoice_number": "INV-1001",
    "supplier": "Example Supplier",
    "amount": 12500.0
  },
  "confidence": {
    "invoice_number": 0.98,
    "supplier": 0.93,
    "amount": 0.91
  }
}
```

---

## Validate Document

### `GET /api/documents/{document_id}/validate`

Returns policy validation.

Possible results:

```text
PASS
FAIL
REVIEW
```

Example:

```json
{
  "document_id": "doc_001",
  "status": "PASS",
  "policy_id": "policy_001",
  "policy_version": "v3",
  "issues": [],
  "evidence": [
    {
      "source": "expense-policy.pdf",
      "reference": "Section 4.2"
    }
  ]
}
```

RAG retrieval must remain restricted by organization, domain and applicable policy version.

---

## Approve Document

### `POST /api/documents/{document_id}/approve`

Role: `APPROVER`

Request:

```json
{
  "comment": "Verified and approved."
}
```

Response:

```json
{
  "document_id": "doc_001",
  "status": "APPROVED",
  "decision": "APPROVED",
  "comment": "Verified and approved."
}
```

---

## Reject Document

### `POST /api/documents/{document_id}/reject`

Role: `APPROVER`

Request:

```json
{
  "comment": "Missing required information."
}
```

Response:

```json
{
  "document_id": "doc_001",
  "status": "REJECTED",
  "decision": "REJECTED",
  "comment": "Missing required information."
}
```

---

# 7. Other Planned APIs

### Policies

```http
GET  /api/policies
POST /api/policies
POST /api/policies/{policy_id}/backtest
```

Used for policy management and the future backtesting differentiator.

### Chatbot

```http
POST /api/chatbot/query
```

Used for status and policy questions.

### Audit

```http
GET /api/audit/{document_id}
```

Returns the document's audit history.

### Admin

```http
GET /api/admin/users
PUT /api/admin/users/{user_id}
```

Used for user and role management.

---

# 8. Document Status

The backend should use a controlled set of workflow states.

Initial states:

```text
UPLOADED
PROCESSING
CLASSIFIED
FAILED
```

Later states may include:

```text
VALIDATED
REVIEW_REQUIRED
PENDING_APPROVAL
APPROVED
REJECTED
COMPLETED
```

The exact state transition rules belong to the workflow module.

---

# 9. Frontend ↔ Backend Responsibility

### Frontend

```text
Collect input
   ↓
Call API
   ↓
Show loading state
   ↓
Display API result
   ↓
Display API error
```

### Backend

```text
Authenticate
   ↓
Authorize
   ↓
Validate request
   ↓
Run business logic
   ↓
Call AI/OCR/RAG when required
   ↓
Save result
   ↓
Return consistent response
```

The frontend must **not** implement business rules that belong to the backend.

---

# 10. Simple Team Rules

1. Do not invent a new endpoint when an existing endpoint already covers the operation.
2. Do not change request/response fields without updating this document and informing the other side.
3. Frontend uses API responses as the source of truth for document state.
4. Backend owns authentication, authorization, validation and workflow rules.
5. AI providers such as Jev or an LLM remain behind the backend API.
6. Every new endpoint should define its method, request, response, authentication and common errors.

---

## 11. Sprint 1 Reference Flow

```text
User logs in
   ↓
POST /api/auth/login
   ↓
Receive JWT
   ↓
POST /api/documents
   ↓
Receive document_id
   ↓
POST /api/documents/{id}/classify
   ↓
Receive category + confidence
   ↓
GET /api/documents/{id}
   ↓
Frontend shows final result
```

This is the main contract the team needs for the current mid-evaluation slice.
