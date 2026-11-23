"""Document visibility and the org-admin / system-admin permission split."""
from types import SimpleNamespace

import pytest

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.models.document import DocumentStatus
from services.document_access import can_view_document


def doc(**kw):
    base = dict(uploaded_by="sub1", assigned_reviewer_id=None, assigned_approver_id=None, status=DocumentStatus.UPLOADED)
    return SimpleNamespace(**{**base, **kw})


def test_submitter_sees_only_own_documents():
    assert can_view_document(doc(), "sub1", "SUBMITTER")
    assert not can_view_document(doc(), "sub2", "SUBMITTER")


def test_reviewer_sees_assigned_or_queued_documents_only():
    assert can_view_document(doc(assigned_reviewer_id="r1"), "r1", "REVIEWER")
    assert can_view_document(doc(status=DocumentStatus.SUBMITTED), "r1", "REVIEWER")  # unassigned, in queue
    assert not can_view_document(doc(), "r1", "REVIEWER")  # not submitted yet
    assert not can_view_document(doc(status=DocumentStatus.SUBMITTED, assigned_reviewer_id="r2"), "r1", "REVIEWER")


def test_approver_sees_assigned_or_queued_documents_only():
    assert can_view_document(doc(assigned_approver_id="a1"), "a1", "APPROVER")
    assert can_view_document(doc(status=DocumentStatus.PENDING_APPROVAL), "a1", "APPROVER")
    assert not can_view_document(doc(status=DocumentStatus.SUBMITTED), "a1", "APPROVER")
    assert not can_view_document(doc(status=DocumentStatus.PENDING_APPROVAL, assigned_approver_id="a2"), "a1", "APPROVER")


@pytest.mark.parametrize("role", ["ORG_ADMIN", "SYSTEM_ADMIN", "NOBODY"])
def test_admins_and_unknown_roles_see_no_documents(role):
    assert not can_view_document(doc(assigned_reviewer_id="x"), "x", role)


def test_org_admin_manages_people_and_policies_only():
    perms = ROLE_PERMISSIONS["ORG_ADMIN"]
    assert Permission.ADMIN_USERS_MANAGE in perms and Permission.POLICIES_ADMIN in perms
    assert Permission.DOCUMENTS_READ not in perms and Permission.WORKFLOW_DECIDE not in perms
    assert Permission.ADMIN_ORGS_MANAGE not in perms


def test_only_system_admin_manages_organizations():
    owners = [role for role, perms in ROLE_PERMISSIONS.items() if Permission.ADMIN_ORGS_MANAGE in perms]
    assert owners == ["SYSTEM_ADMIN"]
