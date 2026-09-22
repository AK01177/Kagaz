"""
Tests for BE-03: document metadata storage and retrieval.
Run with: pytest backend/tests/test_document_metadata.py

Uses an in-memory SQLite DB so the suite runs without a Postgres
instance — no infra setup needed to verify this issue's logic.
"""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.document import DocumentStatus
from app.schemas.document import DocumentMetadataCreate, DocumentStatusUpdate
from app.crud.document import create_document_metadata, get_document_metadata, update_document_status


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_create_and_retrieve_document_metadata(db_session):
    org_id = uuid.uuid4()
    data = DocumentMetadataCreate(
        organization_id=org_id,
        uploaded_by=uuid.uuid4(),
        filename="invoice.pdf",
        file_type="application/pdf",
        file_size=204800,
        storage_path="s3://kagaz-docs/org123/invoice.pdf",
    )

    created = create_document_metadata(db_session, data)

    assert created.id is not None
    assert created.status == DocumentStatus.UPLOADED

    fetched = get_document_metadata(db_session, created.id, org_id)
    assert fetched is not None
    assert fetched.filename == "invoice.pdf"
    assert fetched.file_size == 204800


def test_metadata_scoped_to_organization(db_session):
    """A document must not be retrievable using the wrong organization_id (tenant isolation)."""
    data = DocumentMetadataCreate(
        organization_id=uuid.uuid4(),
        uploaded_by=uuid.uuid4(),
        filename="contract.pdf",
        file_type="application/pdf",
        file_size=51200,
        storage_path="s3://kagaz-docs/org456/contract.pdf",
    )
    created = create_document_metadata(db_session, data)

    wrong_org_id = uuid.uuid4()
    result = get_document_metadata(db_session, created.id, wrong_org_id)

    assert result is None


def test_update_status_after_classification(db_session):
    data = DocumentMetadataCreate(
        organization_id=uuid.uuid4(),
        uploaded_by=uuid.uuid4(),
        filename="transcript.pdf",
        file_type="application/pdf",
        file_size=102400,
        storage_path="s3://kagaz-docs/orgabc/transcript.pdf",
    )
    created = create_document_metadata(db_session, data)

    update = DocumentStatusUpdate(
        status=DocumentStatus.CLASSIFIED,
        classification="academic_transcript",
        classification_confidence=0.91,
    )
    updated = update_document_status(db_session, created.id, created.organization_id, update)

    assert updated.status == DocumentStatus.CLASSIFIED
    assert updated.classification == "academic_transcript"
    assert updated.classification_confidence == 0.91
