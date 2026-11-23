"""Re-classifying a document must not pull it back out of the review workflow."""
from types import SimpleNamespace

import pytest

from api.documents import _reset_status_before_review
from app.models.document import DocumentStatus


@pytest.mark.parametrize("status", [DocumentStatus.IN_REVIEW, DocumentStatus.PENDING_APPROVAL, DocumentStatus.APPROVED])
def test_workflow_statuses_are_left_alone(status):
    doc = SimpleNamespace(status=status)
    _reset_status_before_review(doc, has_extraction=True)
    assert doc.status == status


def test_pre_review_status_is_reset():
    doc = SimpleNamespace(status=DocumentStatus.VALIDATED)
    _reset_status_before_review(doc, has_extraction=True)
    assert doc.status == DocumentStatus.EXTRACTED
    _reset_status_before_review(doc, has_extraction=False)
    assert doc.status == DocumentStatus.CLASSIFIED
