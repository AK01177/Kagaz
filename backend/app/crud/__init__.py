"""CRUD modules for Kagaz backend."""
from app.crud.document import (
    create_document_metadata,
    get_document_metadata,
    update_document_status,
)
from app.crud.extraction import (
    create_extraction,
    create_extractions_bulk,
    get_extractions_by_document,
    get_document_extractions_summary,
    delete_extractions_by_document,
)
from app.crud.organization import (
    create_organization,
    get_organization,
    get_organization_by_slug,
)
from app.crud.user import (
    create_user,
    get_user,
    get_user_by_email,
    get_user_by_provider_subject,
    create_user_provider_mapping,
)
from app.crud.membership import (
    create_membership,
    get_membership,
    get_user_memberships,
    get_organization_memberships,
)
from app.crud.policy import (
    create_policy,
    get_policy,
    list_policies,
    update_policy,
    deactivate_policy,
    list_policy_versions,
)

__all__ = [
    "create_document_metadata",
    "get_document_metadata",
    "update_document_status",
    "create_extraction",
    "create_extractions_bulk",
    "get_extractions_by_document",
    "get_document_extractions_summary",
    "delete_extractions_by_document",
    "create_organization",
    "get_organization",
    "get_organization_by_slug",
    "create_user",
    "get_user",
    "get_user_by_email",
    "get_user_by_provider_subject",
    "create_user_provider_mapping",
    "create_membership",
    "get_membership",
    "get_user_memberships",
    "get_organization_memberships",
    "create_policy",
    "get_policy",
    "list_policies",
    "update_policy",
    "deactivate_policy",
    "list_policy_versions",
]
