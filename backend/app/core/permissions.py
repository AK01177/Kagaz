"""Canonical RBAC Role-Permission Matrix for Kagaz FastAPI endpoints."""
from __future__ import annotations

import enum
from typing import Collection, Mapping


class Permission(str, enum.Enum):
    """Named capabilities enforced by FastAPI dependencies and domain services."""

    # Document intake, inspection, classification, extraction, and validation
    DOCUMENTS_UPLOAD = "documents:upload"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_CLASSIFY = "documents:classify"
    DOCUMENTS_CORRECT_CLASSIFICATION = "documents:correct_classification"
    DOCUMENTS_READ_EXTRACTION = "documents:read_extraction"
    DOCUMENTS_RUN_EXTRACTION = "documents:run_extraction"
    DOCUMENTS_VALIDATE = "documents:validate"
    DOCUMENTS_VALIDATE_POLICY = "documents:validate_policy"

    # Policy knowledge management
    POLICIES_READ = "policies:read"
    POLICIES_ADMIN = "policies:admin"

    # Workflow review vs approval separation
    WORKFLOW_SUBMIT = "workflow:submit"
    WORKFLOW_RESUBMIT = "workflow:resubmit"
    WORKFLOW_VIEW_REVIEWERS = "workflow:view_reviewers"
    WORKFLOW_VIEW_STATUS = "workflow:view_status"
    WORKFLOW_REVIEW_QUEUE = "workflow:review_queue"
    WORKFLOW_APPROVAL_QUEUE = "workflow:approval_queue"
    WORKFLOW_ASSIGN_REVIEWER = "workflow:assign_reviewer"
    WORKFLOW_REQUEST_CHANGES = "workflow:request_changes"
    WORKFLOW_SUBMIT_FOR_APPROVAL = "workflow:submit_for_approval"
    WORKFLOW_REVIEW_DETAIL = "workflow:review_detail"
    WORKFLOW_REVIEW_COMMENT = "workflow:review_comment"
    WORKFLOW_DECIDE = "workflow:decide"

    # Audit, assistant, and notifications
    AUDIT_READ = "audit:read"
    ASSISTANT_QUERY = "assistant:query"
    NOTIFICATIONS_READ = "notifications:read"

    # Organization administration
    ADMIN_ORG_READ = "admin:org_read"
    ADMIN_USERS_READ = "admin:users_read"
    ADMIN_USERS_MANAGE = "admin:users_manage"


_COMMON_READ_PERMISSIONS = frozenset(
    {
        Permission.DOCUMENTS_READ,
        Permission.POLICIES_READ,
        Permission.WORKFLOW_VIEW_STATUS,
        Permission.WORKFLOW_REVIEW_DETAIL,
        Permission.AUDIT_READ,
        Permission.ASSISTANT_QUERY,
        Permission.NOTIFICATIONS_READ,
    }
)

_ORG_ADMIN_PERMISSIONS = frozenset(Permission)

ROLE_PERMISSIONS: Mapping[str, frozenset[Permission]] = {
    "SUBMITTER": _COMMON_READ_PERMISSIONS
    | frozenset(
        {
            Permission.DOCUMENTS_UPLOAD,
            Permission.DOCUMENTS_VALIDATE,
            Permission.DOCUMENTS_VALIDATE_POLICY,
            Permission.WORKFLOW_SUBMIT,
            Permission.WORKFLOW_RESUBMIT,
            Permission.WORKFLOW_VIEW_REVIEWERS,
        }
    ),
    "REVIEWER": _COMMON_READ_PERMISSIONS
    | frozenset(
        {
            Permission.DOCUMENTS_CLASSIFY,
            Permission.DOCUMENTS_CORRECT_CLASSIFICATION,
            Permission.DOCUMENTS_READ_EXTRACTION,
            Permission.DOCUMENTS_RUN_EXTRACTION,
            Permission.DOCUMENTS_VALIDATE,
            Permission.DOCUMENTS_VALIDATE_POLICY,
            Permission.WORKFLOW_VIEW_REVIEWERS,
            Permission.WORKFLOW_REVIEW_QUEUE,
            Permission.WORKFLOW_ASSIGN_REVIEWER,
            Permission.WORKFLOW_REQUEST_CHANGES,
            Permission.WORKFLOW_SUBMIT_FOR_APPROVAL,
            Permission.WORKFLOW_REVIEW_COMMENT,
        }
    ),
    "APPROVER": _COMMON_READ_PERMISSIONS
    | frozenset(
        {
            Permission.DOCUMENTS_READ_EXTRACTION,
            Permission.DOCUMENTS_VALIDATE_POLICY,
            Permission.WORKFLOW_VIEW_REVIEWERS,
            Permission.WORKFLOW_REVIEW_QUEUE,
            Permission.WORKFLOW_APPROVAL_QUEUE,
            Permission.WORKFLOW_REQUEST_CHANGES,
            Permission.WORKFLOW_REVIEW_COMMENT,
            Permission.WORKFLOW_DECIDE,
        }
    ),
    "COMPLIANCE": _COMMON_READ_PERMISSIONS
    | frozenset(
        {
            Permission.DOCUMENTS_READ_EXTRACTION,
            Permission.DOCUMENTS_VALIDATE,
            Permission.DOCUMENTS_VALIDATE_POLICY,
        }
    ),
    "AUDITOR": _COMMON_READ_PERMISSIONS
    | frozenset(
        {
            Permission.DOCUMENTS_READ_EXTRACTION,
        }
    ),
    "ORG_ADMIN": _ORG_ADMIN_PERMISSIONS,
    "SYSTEM_ADMIN": _ORG_ADMIN_PERMISSIONS,
}

PERMISSION_ERROR_DETAILS: Mapping[Permission, tuple[str, str]] = {
    Permission.DOCUMENTS_UPLOAD: (
        "UPLOAD_FORBIDDEN",
        "You do not have permission to upload documents.",
    ),
    Permission.DOCUMENTS_READ: (
        "DOCUMENT_READ_FORBIDDEN",
        "You do not have permission to read documents.",
    ),
    Permission.DOCUMENTS_CLASSIFY: (
        "CLASSIFICATION_FORBIDDEN",
        "An active reviewer or administrator role is required to classify documents.",
    ),
    Permission.DOCUMENTS_CORRECT_CLASSIFICATION: (
        "REVIEW_FORBIDDEN",
        "An active reviewer or administrator role is required to correct classifications.",
    ),
    Permission.DOCUMENTS_READ_EXTRACTION: (
        "EXTRACTION_READ_FORBIDDEN",
        "You do not have permission to view extracted document fields.",
    ),
    Permission.DOCUMENTS_RUN_EXTRACTION: (
        "EXTRACTION_FORBIDDEN",
        "An active reviewer or administrator role is required to run extraction.",
    ),
    Permission.DOCUMENTS_VALIDATE: (
        "VALIDATION_FORBIDDEN",
        "You do not have permission to validate documents.",
    ),
    Permission.DOCUMENTS_VALIDATE_POLICY: (
        "POLICY_VALIDATION_FORBIDDEN",
        "You do not have permission to run policy validation.",
    ),
    Permission.POLICIES_READ: (
        "POLICY_READ_FORBIDDEN",
        "You do not have permission to read organization policies.",
    ),
    Permission.POLICIES_ADMIN: (
        "POLICY_ADMIN_REQUIRED",
        "An active organization admin account is required to manage policies.",
    ),
    Permission.WORKFLOW_SUBMIT: (
        "WORKFLOW_SUBMIT_FORBIDDEN",
        "You do not have permission to submit documents for review.",
    ),
    Permission.WORKFLOW_RESUBMIT: (
        "WORKFLOW_RESUBMIT_FORBIDDEN",
        "You do not have permission to resubmit documents.",
    ),
    Permission.WORKFLOW_VIEW_REVIEWERS: (
        "WORKFLOW_REVIEWERS_FORBIDDEN",
        "You do not have permission to list eligible reviewers.",
    ),
    Permission.WORKFLOW_VIEW_STATUS: (
        "WORKFLOW_READ_FORBIDDEN",
        "You do not have permission to view document workflow status.",
    ),
    Permission.WORKFLOW_REVIEW_QUEUE: (
        "REVIEW_QUEUE_FORBIDDEN",
        "An active reviewer or approver role is required to access the review queue.",
    ),
    Permission.WORKFLOW_APPROVAL_QUEUE: (
        "APPROVAL_QUEUE_FORBIDDEN",
        "An active approver or administrator role is required to access the approval queue.",
    ),
    Permission.WORKFLOW_ASSIGN_REVIEWER: (
        "ASSIGN_REVIEWER_FORBIDDEN",
        "An active reviewer or administrator role is required to assign reviewers.",
    ),
    Permission.WORKFLOW_REQUEST_CHANGES: (
        "REQUEST_CHANGES_FORBIDDEN",
        "An active reviewer or approver role is required to request changes.",
    ),
    Permission.WORKFLOW_SUBMIT_FOR_APPROVAL: (
        "SUBMIT_FOR_APPROVAL_FORBIDDEN",
        "An active reviewer or administrator role is required to submit documents for approval.",
    ),
    Permission.WORKFLOW_REVIEW_DETAIL: (
        "REVIEW_DETAIL_FORBIDDEN",
        "You do not have permission to access review details.",
    ),
    Permission.WORKFLOW_REVIEW_COMMENT: (
        "REVIEW_COMMENT_FORBIDDEN",
        "An active reviewer or approver role is required to submit review comments.",
    ),
    Permission.WORKFLOW_DECIDE: (
        "APPROVAL_FORBIDDEN",
        "An authorized approver role is required to approve or reject documents.",
    ),
    Permission.AUDIT_READ: (
        "AUDIT_READ_FORBIDDEN",
        "You do not have permission to inspect document audit history.",
    ),
    Permission.ASSISTANT_QUERY: (
        "ASSISTANT_FORBIDDEN",
        "You do not have permission to query the document assistant.",
    ),
    Permission.NOTIFICATIONS_READ: (
        "NOTIFICATIONS_FORBIDDEN",
        "You do not have permission to access notifications.",
    ),
    Permission.ADMIN_ORG_READ: (
        "ADMIN_FORBIDDEN",
        "An active organization administrator account is required.",
    ),
    Permission.ADMIN_USERS_READ: (
        "ADMIN_FORBIDDEN",
        "An active organization administrator account is required.",
    ),
    Permission.ADMIN_USERS_MANAGE: (
        "ADMIN_FORBIDDEN",
        "An active organization administrator account is required.",
    ),
}


def get_permissions_for_role(role: str) -> frozenset[Permission]:
    """Return the immutable permission set granted to a canonical role."""
    normalized = (role or "").strip().upper()
    return ROLE_PERMISSIONS.get(normalized, frozenset())


def roles_with_permission(permission: Permission) -> frozenset[str]:
    """Return every role granted a given permission by the matrix."""
    return frozenset(
        role for role, perms in ROLE_PERMISSIONS.items() if permission in perms
    )


def identity_has_permission(
    identity: Mapping[str, object],
    permission: Permission | str,
) -> bool:
    """Evaluate role-matrix grants and explicit server-verified permission grants."""
    perm_enum = permission if isinstance(permission, Permission) else Permission(permission)
    role = str(identity.get("role") or "").strip().upper()
    if perm_enum in get_permissions_for_role(role):
        return True

    explicit: Collection[str] = identity.get("permissions") or ()  # type: ignore[assignment]
    if isinstance(explicit, (list, tuple, set, frozenset)):
        return perm_enum.value in {str(item).strip() for item in explicit}
    return False
