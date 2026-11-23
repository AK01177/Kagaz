"""Who may view a document. One rule used by every document endpoint.

- SUBMITTER: only documents they uploaded.
- REVIEWER: documents assigned to them, or unassigned documents waiting in the review queue.
- APPROVER: documents assigned to them, or unassigned documents waiting in the approval queue.
- Everyone else (including org admins): no document access.
"""
from app.models.document import DocumentStatus

_REVIEW_QUEUE_UNASSIGNED = {DocumentStatus.SUBMITTED}
_APPROVAL_QUEUE_UNASSIGNED = {DocumentStatus.IN_REVIEW, DocumentStatus.PENDING_APPROVAL}


def can_view_document(document, actor_id: str, role: str) -> bool:
    role = str(role or "").strip().upper()
    if role == "SUBMITTER":
        return document.uploaded_by == actor_id
    if role == "REVIEWER":
        return document.assigned_reviewer_id == actor_id or (
            document.assigned_reviewer_id is None and document.status in _REVIEW_QUEUE_UNASSIGNED
        )
    if role == "APPROVER":
        return document.assigned_approver_id == actor_id or (
            document.assigned_approver_id is None and document.status in _APPROVAL_QUEUE_UNASSIGNED
        )
    return False
