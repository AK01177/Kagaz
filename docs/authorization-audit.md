# Backend Endpoint Authorization Audit & Role-Permission Matrix

This document records the backend authorization architecture and per-endpoint security audit for Kagaz (`backend/`).

Frontend navigation hiding is treated strictly as a UX convenience and **never** as an access control boundary. Every protected FastAPI endpoint enforces:

1. **Trusted Identity (`401 Unauthorized`)**: Valid server-verified credentials resolved from the database / signed JWT (`get_current_user` in `backend/api/auth.py`). Caller-supplied `role`, `permissions`, or unauthorized `organization_id` headers are never trusted as authority.
2. **Role-Permission Matrix (`403 Forbidden`)**: Reusable `require_permission(Permission.<CAP>)` and named dependencies in `backend/api/auth.py` backed by `ROLE_PERMISSIONS` in `backend/app/core/permissions.py`.
3. **Tenant Isolation (`403 Forbidden`)**: Active organization membership resolution and fail-closed `require_organization_membership(...)` / service-level tenant checks.
4. **Object & Workflow State Guards (`403 Forbidden` / `409 Conflict`)**:
   - `SUBMITTER` read/download/validate operations on `/api/documents/{id}*` are restricted to documents uploaded by that submitter.
   - `APPROVER` decisions (`/approve`, `/reject`) are permitted **only** on eligible documents in the caller's active organization (`IN_REVIEW` or `PENDING_APPROVAL`) and are blocked if already finalized or assigned to a different approver.

---

## Consistent `403 Forbidden` Error Format

All FastAPI authorization failures raise `HTTPException(status_code=403, detail={"code": ..., "message": ...})`, which `backend/main.py` normalizes into:

```json
{
  "error": {
    "code": "APPROVAL_FORBIDDEN",
    "message": "An authorized approver role is required to approve or reject documents."
  }
}
```

Tenant isolation and ownership denials follow the same envelope (`TENANT_ACCESS_DENIED`, `ADMIN_TENANT_FORBIDDEN`, `DOCUMENT_ACCESS_FORBIDDEN`, `MEMBERSHIP_REQUIRED`, `SYSTEM_ADMIN_REQUIRED`).

---

## Canonical Role-Permission Matrix (`backend/app/core/permissions.py`)

Roles defined in `MembershipRole`: `SUBMITTER`, `REVIEWER`, `APPROVER`, `COMPLIANCE`, `AUDITOR`, `ORG_ADMIN`, `SYSTEM_ADMIN`.

| Permission | `SUBMITTER` | `REVIEWER` | `APPROVER` | `COMPLIANCE` | `AUDITOR` | `ORG_ADMIN` | `SYSTEM_ADMIN` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `documents:upload` | Yes | - | - | - | - | Yes | Yes |
| `documents:read` | Yes (own) | Yes | Yes | Yes | Yes | Yes | Yes |
| `documents:classify` | - | Yes | - | - | - | Yes | Yes |
| `documents:correct_classification` | - | Yes | - | - | - | Yes | Yes |
| `documents:read_extraction` | - | Yes | Yes | Yes | Yes | Yes | Yes |
| `documents:run_extraction` | - | Yes | - | - | - | Yes | Yes |
| `documents:validate` | Yes (own) | Yes | - | Yes | - | Yes | Yes |
| `documents:validate_policy` | Yes (own) | Yes | Yes | Yes | - | Yes | Yes |
| `policies:read` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `policies:admin` | - | - | - | - | - | Yes | Yes |
| `workflow:submit` | Yes | - | - | - | - | Yes | Yes |
| `workflow:resubmit` | Yes | - | - | - | - | Yes | Yes |
| `workflow:view_reviewers` | Yes | Yes | Yes | - | - | Yes | Yes |
| `workflow:view_status` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `workflow:review_queue` | - | Yes | Yes | - | - | Yes | Yes |
| `workflow:approval_queue` | - | - | Yes | - | - | Yes | Yes |
| `workflow:assign_reviewer` | - | Yes | - | - | - | Yes | Yes |
| `workflow:request_changes` | - | Yes | Yes | - | - | Yes | Yes |
| `workflow:submit_for_approval` | - | Yes | - | - | - | Yes | Yes |
| `workflow:review_detail` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `workflow:review_comment` | - | Yes | Yes | - | - | Yes | Yes |
| `workflow:decide` | - | - | Yes | - | - | Yes | Yes |
| `audit:read` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `assistant:query` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `notifications:read` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `admin:org_read` | - | - | - | - | - | Yes | Yes |
| `admin:users_read` | - | - | - | - | - | Yes | Yes |
| `admin:users_manage` | - | - | - | - | - | Yes | Yes |

*(Note: Individual users can also be granted an explicit server-verified permission via signed backend/DB authorization metadata, evaluated by `identity_has_permission`, without trusting client-supplied claims.)*

---

## Reviewer vs. Approver Responsibility Separation

| Responsibility | `REVIEWER` | `APPROVER` |
|---|---|---|
| Inspect review queue & review evidence | Yes | Yes |
| Assign reviewers (`POST /assign`) | Yes | No (`403`) |
| Classify / correct classification / re-extract | Yes | No (`403`) |
| Request changes / add review comments | Yes | Yes |
| Submit document for final approval (`POST /submit-for-approval`) | Yes | No (`403`) |
| Inspect final approval queue (`GET /workflow/approval-queue`) | No (`403`) | Yes |
| Issue final approval / rejection decision (`POST /approve`, `POST /reject`) | No (`403`) | Yes (eligible docs only) |
| Manage organization policies or admin users (`/api/admin/*`, `policies:admin`) | No (`403`) | No (`403`) |

---

## Endpoint Authorization Audit (`main.app`)

### Health & Authentication (`backend/api/health.py`, `backend/api/auth.py`)

| Method & Path | Dependency | Permitted Roles | Tenant / Object / State Checks |
|---|---|---|---|
| `GET /api/health` | Public | Public | Non-sensitive health check only |
| `POST /api/auth/login` | Public | Registered active users | Verifies password hash; resolves active membership server-side |
| `GET /api/auth/me` | `get_current_user` | Any authenticated active member | Resolves user, active org, role, permissions from DB/token |
| `GET /api/auth/memberships` | `get_current_user` | Any authenticated active member | Lists caller's verified active memberships only |

### Document Ingestion, Metadata, Classification, Extraction & Validation (`backend/api/documents.py`, `backend/app/api/routes/policy_validation.py`)

| Method & Path | Dependency / Permission | Permitted Roles | Tenant / Object / State Checks |
|---|---|---|---|
| `POST /api/documents` | `require_submitter` (`documents:upload`) | `SUBMITTER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Stamps `organization_id` and `uploaded_by` from verified identity |
| `GET /api/documents/{document_id}/file` | `require_document_reader` (`documents:read`) | All active org roles | Active org match; `SUBMITTER` restricted to own `uploaded_by` |
| `GET /api/documents/{document_id}` | `require_document_reader` (`documents:read`) | All active org roles | Active org match; `SUBMITTER` restricted to own `uploaded_by` |
| `POST /api/documents/{document_id}/classify` | `require_classifier` (`documents:classify`) | `REVIEWER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Active org match |
| `PATCH /api/documents/{document_id}/classification` | `require_reviewer` (`documents:correct_classification`) | `REVIEWER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Active org match; records audit event |
| `GET /api/documents/{document_id}/extract` | `require_extraction_reader` (`documents:read_extraction`) | `REVIEWER`, `APPROVER`, `COMPLIANCE`, `AUDITOR`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Active org match |
| `POST /api/documents/{document_id}/extract` | `require_extraction_runner` (`documents:run_extraction`) | `REVIEWER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Active org match; records audit event |
| `POST /api/documents/{document_id}/validate` | `require_validator` (`documents:validate`) | `SUBMITTER`, `REVIEWER`, `COMPLIANCE`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Active org match; `SUBMITTER` restricted to own docs |
| `GET /api/documents/{document_id}/validate` | `require_document_reader` (`documents:read`) | All active org roles | Active org match; `SUBMITTER` restricted to own docs |
| `POST /api/documents/{document_id}/validate-policy` | `require_permission(Permission.DOCUMENTS_VALIDATE_POLICY)` | `SUBMITTER`, `REVIEWER`, `APPROVER`, `COMPLIANCE`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Active org match; read-only `AUDITOR` rejected with `403` |
| `GET /documents/{document_id}` *(unmounted legacy router in `app/api/routes/documents.py`)* | `require_permission(Permission.DOCUMENTS_READ)` | All active org roles | Active org match via verified identity |

### Policy Knowledge Management & Vector Retrieval (`backend/api/policies.py`, `backend/app/api/routes/policies.py`)

| Method & Path | Dependency / Permission | Permitted Roles | Tenant / Object / State Checks |
|---|---|---|---|
| `GET /api/policies` | `require_policy_reader` (`policies:read`) | All active org roles | Filtered by caller's active `organization_id` |
| `GET /api/policies/{policy_id}` | `require_policy_reader` (`policies:read`) | All active org roles | Policy must belong to caller's active `organization_id` |
| `POST /api/policies/retrieve` | `require_policy_reader` (`policies:read`) | All active org roles | Org-scoped vector search + confidentiality classification gate |
| `POST /api/policies` | `require_policy_admin` (`policies:admin`) | `ORG_ADMIN`, `SYSTEM_ADMIN` | Created inside caller's active `organization_id` |
| `PUT /api/policies/{policy_id}` | `require_policy_admin` (`policies:admin`) | `ORG_ADMIN`, `SYSTEM_ADMIN` | Policy must belong to caller's active `organization_id` |
| `DELETE /api/policies/{policy_id}` | `require_policy_admin` (`policies:admin`) | `ORG_ADMIN`, `SYSTEM_ADMIN` | Policy must belong to caller's active `organization_id` |
| `GET /api/policies/{policy_id}/versions` *(both routers)* | `require_policy_admin` (`policies:admin`) | `ORG_ADMIN`, `SYSTEM_ADMIN` | Policy must belong to caller's active `organization_id` |
| `POST /api/policies/ingest` | `require_policy_admin` (`policies:admin`) | `ORG_ADMIN`, `SYSTEM_ADMIN` | Active org check in upload & Celery/ingestion pipeline |
| `POST /api/policies/{policy_id}/versions/{version_id}/retry` | `require_policy_admin` (`policies:admin`) | `ORG_ADMIN`, `SYSTEM_ADMIN` | Policy + source document must belong to caller's active org |

### Document Workflow, Review, Approval & Audit (`backend/app/api/routes/workflow.py`)

| Method & Path | Dependency / Permission | Permitted Roles | Tenant / Object / State Checks |
|---|---|---|---|
| `GET /api/documents/workflow/review-queue` | `workflow:review_queue` | `REVIEWER`, `APPROVER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped queue |
| `GET /api/documents/workflow/approval-queue` | `workflow:approval_queue` | `APPROVER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped `IN_REVIEW` / `PENDING_APPROVAL` docs; respects `assigned_approver_id` |
| `GET /api/documents/workflow/reviewers` | `workflow:view_reviewers` | `SUBMITTER`, `REVIEWER`, `APPROVER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Lists active `REVIEWER` members of caller's org only |
| `GET /api/documents/{document_id}/workflow` | `workflow:view_status` | All active org roles | Org-scoped; `SUBMITTER` restricted to own documents |
| `POST /api/documents/{document_id}/submit` | `workflow:submit` | `SUBMITTER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped; non-admin `SUBMITTER` only on own docs; valid state transition |
| `POST /api/documents/{document_id}/assign` | `workflow:assign_reviewer` | `REVIEWER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped; assignee must be active `REVIEWER` in same org |
| `POST /api/documents/{document_id}/request-changes` | `workflow:request_changes` | `REVIEWER`, `APPROVER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped; role/state check + assignee guard + mandatory comment |
| `POST /api/documents/{document_id}/resubmit` | `workflow:resubmit` | `SUBMITTER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped; `CHANGES_REQUESTED` only; non-admin `SUBMITTER` only on own docs |
| `POST /api/documents/{document_id}/submit-for-approval` | `workflow:submit_for_approval` | `REVIEWER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped; `IN_REVIEW` docs; assigned approver must be active `APPROVER` in org |
| `GET /api/documents/{document_id}/review` | `workflow:review_detail` | All active org roles | Org-scoped; `SUBMITTER` restricted to own documents |
| `POST /api/documents/{document_id}/comments` | `workflow:review_comment` | `REVIEWER`, `APPROVER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped; assigned reviewer/approver or admin |
| `POST /api/documents/{document_id}/approve` | `workflow:decide` | `APPROVER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped; eligible (`IN_REVIEW` / `PENDING_APPROVAL`) docs; non-duplicate; assignee guard |
| `POST /api/documents/{document_id}/reject` | `workflow:decide` | `APPROVER`, `ORG_ADMIN`, `SYSTEM_ADMIN` | Org-scoped; eligible (`IN_REVIEW` / `PENDING_APPROVAL`) docs; non-duplicate; assignee guard |
| `GET /api/audit/{document_id}` | `require_audit_reader` (`audit:read`) | All active org roles | Org-scoped; chronological read-only audit history; `SUBMITTER` restricted to own docs |

### Assistant, Notifications & Organization Admin (`assistant.py`, `notifications.py`, `admin.py`)

| Method & Path | Dependency / Permission | Permitted Roles | Tenant / Object / State Checks |
|---|---|---|---|
| `POST /api/documents/{document_id}/assistant/query` (+ `/assistant` alias) | `assistant:query` | All active org roles | Org-scoped document/policy grounding; `SUBMITTER` restricted to own docs |
| `GET /api/notifications` | `notifications:read` | All active org roles | Filtered to caller's `sub` and active `organization_id` |
| `PATCH /api/notifications/{notification_id}/read` (+ `POST`) | `notifications:read` | All active org roles | Recipient `sub` and active `organization_id` must match |
| `POST /api/notifications/read-all` | `notifications:read` | All active org roles | Scoped to caller's `sub` and active `organization_id` |
| `GET /api/admin/organization` | `admin:org_read` | `ORG_ADMIN`, `SYSTEM_ADMIN` | Rejects cross-org `?organization_id=` with `403 ADMIN_TENANT_FORBIDDEN` |
| `GET /api/admin/users` | `admin:users_read` | `ORG_ADMIN`, `SYSTEM_ADMIN` | Rejects cross-org `?organization_id=` with `403 ADMIN_TENANT_FORBIDDEN` |
| `PUT /api/admin/users/{user_id}` | `admin:users_manage` | `ORG_ADMIN`, `SYSTEM_ADMIN` | Rejects cross-org `organization_id` (`403`) or foreign user (`404`); blocks non-`SYSTEM_ADMIN` from granting `SYSTEM_ADMIN` (`403 SYSTEM_ADMIN_REQUIRED`) |

---

## Gaps Identified & Closed During Audit

1. **`POST /api/documents/{document_id}/classify` lacked a role dependency**: Previously accepted `get_active_organization_id`, allowing any authenticated role (`SUBMITTER`, `AUDITOR`, `APPROVER`) to trigger reclassification. Tightened to `require_classifier` (`Permission.DOCUMENTS_CLASSIFY`).
2. **Coarse `require_workflow_actor` on all workflow/assistant/notification routes**: Previously relied solely on deep service checks after entering route handlers. Replaced with per-route `require_permission(Permission.<CAP>)` dependencies so unauthorized calls fail immediately at FastAPI dependency resolution with consistent `403` payloads.
3. **Policy CRUD endpoints (`backend/api/policies.py`)**: `POST`/`PUT`/`DELETE` previously accepted `require_reviewer` (allowing reviewers/approvers to delete or modify org policies) while `GET` only accepted `require_submitter` (blocking `REVIEWER`/`APPROVER`/`AUDITOR` from listing/reading policies via `/api/policies`). Fixed to `require_policy_admin` for mutations/version-admin and `require_policy_reader` for reads.
4. **Submission/Review/Approval role overlap**: Removed `APPROVER` from `ASSIGN_REVIEWER_CALLER_ROLES` and `POST /api/documents/{id}/extract` from `require_submitter`, tightened `GET /api/documents/{id}/extract` to `require_extraction_reader`, restricted `SUBMITTER` read/download/validate operations to documents uploaded by that submitter, and prevented read-only `AUDITOR` accounts from mutating validation runs via `POST /api/documents/{id}/validate-policy`.
5. **Organization-scoped Admin APIs (`backend/app/api/routes/admin.py`)**: Added tenant-isolated admin endpoints protected by `Permission.ADMIN_*`, ensuring reviewers/submitters/approvers receive `403` and admins cannot inspect or modify memberships in any other organization.
