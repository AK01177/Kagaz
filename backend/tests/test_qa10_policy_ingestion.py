"""QA-10 coverage for PDF extraction, chunk metadata, and vector persistence."""

from io import BytesIO

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.models.policy import EMBEDDING_DIMENSION, PolicyChunk
from tests.test_policy_ingestion import _token, policy_client


def policy_pdf():
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    for page in range(3):
        for line in range(30):
            pdf.drawString(72, 780 - 22 * line, f"Clause {page + 1}.{line + 1}: Keep receipts for travel expenses.")
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def upload_policy(client):
    return client.post(
        "/api/policies/ingest",
        headers={"Authorization": f"Bearer {_token('org-a')}"},
        data={
            "policy_name": "Travel Policy",
            "version": "v1",
            "domain": "finance",
            "document_type": "invoice",
        },
        files={"file": ("travel-policy.pdf", policy_pdf(), "application/pdf")},
    )


def persisted_chunks(session, version_id):
    session.expire_all()
    return session.scalars(
        select(PolicyChunk)
        .where(PolicyChunk.policy_version_id == version_id)
        .order_by(PolicyChunk.chunk_index)
    ).all()


def test_pdf_is_extracted_and_each_chunk_keeps_its_vector_and_source(policy_client, monkeypatch):
    client, session = policy_client
    embedded_texts = []

    def embed(texts):
        embedded_texts.extend(texts)
        return [[float(index + 1)] + [0.0] * (EMBEDDING_DIMENSION - 1) for index in range(len(texts))]

    monkeypatch.setattr("services.policy_ingestion.create_embeddings", embed)
    response = upload_policy(client)

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "ACTIVE"
    chunks = persisted_chunks(session, result["policy_version_id"])
    assert result["chunk_count"] == len(chunks) == len(embedded_texts)
    assert len(chunks) > 1
    assert "Clause 1.1" in chunks[0].content
    assert "Clause 3.30" in chunks[-1].content

    for index, chunk in enumerate(chunks):
        assert chunk.chunk_index == index
        assert chunk.content == embedded_texts[index]
        assert len(chunk.embedding) == EMBEDDING_DIMENSION
        assert list(chunk.embedding) == pytest.approx(
            [float(index + 1)] + [0.0] * (EMBEDDING_DIMENSION - 1)
        )
        expected_metadata = {
            "organization_id": "org-a",
            "policy_id": result["policy_id"],
            "policy_version_id": result["policy_version_id"],
            "version": "v1",
            "domain": "finance",
            "document_type": "invoice",
            "source_document_id": result["source_document_id"],
            "source_filename": "travel-policy.pdf",
            "chunk_index": index,
        }
        for key, expected in expected_metadata.items():
            assert chunk.chunk_metadata[key] == expected


@pytest.mark.parametrize("invalid_response", ["missing_vector", "wrong_dimension"])
def test_invalid_vectors_fail_ingestion_without_saving_chunks(
    policy_client, monkeypatch, invalid_response
):
    client, session = policy_client

    def embed(texts):
        vectors = [[1.0] + [0.0] * (EMBEDDING_DIMENSION - 1) for _ in texts]
        if invalid_response == "missing_vector":
            return vectors[:-1]
        vectors[-1] = vectors[-1][:-1]
        return vectors

    monkeypatch.setattr("services.policy_ingestion.create_embeddings", embed)
    response = upload_policy(client)

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "FAILED"
    assert result["chunk_count"] == 0
    assert result["ingestion_error"]
    assert persisted_chunks(session, result["policy_version_id"]) == []
