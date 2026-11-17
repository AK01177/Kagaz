"""Document type handling when a policy is saved (RAG Phase 3)."""
from app.models.policy import Policy
from tests.test_policy_indexing import V1, auth, embedder, policy_client  # noqa: F401  (fixtures)

TXT_POLICY = b"## 1. Travel\n1.1 Keep every receipt for seven years after payment.\n"


def upload(client, document_type):
    return client.post(
        "/api/policies/ingest",
        headers=auth(),
        data={"policy_name": "Expenses", "version": "v1", "document_type": document_type},
        files={"file": ("policy.txt", TXT_POLICY, "text/plain")},
    )


def test_uploading_with_a_type_in_any_spelling_stores_the_classifier_category(policy_client, embedder):  # noqa: F811
    client, session = policy_client
    response = upload(client, "Invoices")
    assert response.status_code == 201, response.text
    assert session.query(Policy).filter_by(id=response.json()["policy_id"]).one().document_type == "financial"


def test_an_unknown_document_type_is_rejected_before_anything_is_stored(policy_client, embedder):  # noqa: F811
    client, session = policy_client
    response = upload(client, "memo")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "UNKNOWN_DOCUMENT_TYPE" and "financial" in error["message"]
    assert session.query(Policy).count() == 0 and embedder.calls == []


def test_the_text_api_normalises_and_rejects_document_types(policy_client, embedder):  # noqa: F811
    client, session = policy_client
    good = client.post("/api/policies", headers=auth(), json={"name": "A", "domain": "hr", "content": V1, "document_type": "HR Forms"})
    assert good.status_code == 201 and good.json()["document_type"] == "hr_documents"

    bad = client.post("/api/policies", headers=auth(), json={"name": "B", "domain": "hr", "content": V1, "document_type": "memo"})
    assert bad.status_code == 422 and session.query(Policy).count() == 1

    update = client.put(f"/api/policies/{good.json()['id']}", headers=auth(), json={"document_type": "transcript"})
    assert update.status_code == 200 and update.json()["document_type"] == "academics"
