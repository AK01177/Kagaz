"""Embedding client behaviour: normalisation, batching, retries and secrecy (RAG Phase 2)."""
import math

import httpx
import pytest

from app.models.policy import EMBEDDING_DIMENSION
from services import embeddings, gemini_http
from services.embeddings import EmbeddingServiceError, create_embeddings, create_query_embedding

SECRET = "AIza-test-secret-key"


def vector(value: float = 3.0) -> list[float]:
    return [value] + [4.0 * (value / 3.0)] + [0.0] * (EMBEDDING_DIMENSION - 2)


class FakeApi:
    """Replaces httpx.post: replays scripted responses and records every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.requests.append({"url": url, "json": json, "headers": headers})
        item = self.responses.pop(0) if self.responses else self.ok(len(json["requests"]))
        if isinstance(item, Exception):
            raise item
        return item

    @staticmethod
    def ok(count: int, make=vector) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": make()} for _ in range(count)]})


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    fake = FakeApi()
    sleeps = []
    monkeypatch.setattr(gemini_http.httpx, "post", fake)
    monkeypatch.setattr(gemini_http, "_sleep", sleeps.append)
    fake.sleeps = sleeps
    return fake


def test_vectors_are_normalised_and_keep_input_order(api):
    result = create_embeddings(["a", "b"])
    assert len(result) == 2 and len(result[0]) == EMBEDDING_DIMENSION
    assert math.isclose(math.sqrt(sum(x * x for x in result[0])), 1.0)
    assert result[0][:2] == pytest.approx([0.6, 0.8])


def test_documents_and_queries_use_different_task_types(api):
    create_embeddings(["clause"])
    create_query_embedding("question")
    types = [request["json"]["requests"][0]["taskType"] for request in api.requests]
    assert types == ["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
    assert all(r["json"]["requests"][0]["outputDimensionality"] == EMBEDDING_DIMENSION for r in api.requests)


def test_the_api_key_is_sent_in_a_header_and_never_in_the_url(api):
    create_embeddings(["x"])
    request = api.requests[0]
    assert request["headers"]["x-goog-api-key"] == SECRET
    assert SECRET not in request["url"]


def test_more_than_one_hundred_texts_are_sent_in_batches(api):
    assert len(create_embeddings([f"clause {n}" for n in range(250)])) == 250
    assert [len(r["json"]["requests"]) for r in api.requests] == [100, 100, 50]


def test_a_rate_limit_is_retried_and_retry_after_is_honoured(api):
    api.responses = [httpx.Response(429, headers={"retry-after": "7"}, text="slow down"), FakeApi.ok(1)]
    assert len(create_embeddings(["x"])) == 1
    assert api.sleeps == [7.0]


def test_transient_server_and_network_errors_are_retried_with_growing_backoff(api):
    api.responses = [httpx.ConnectTimeout("t"), httpx.Response(503), FakeApi.ok(1)]
    assert len(create_embeddings(["x"])) == 1
    assert api.sleeps == [2.0, 4.0]


def test_gives_up_after_the_attempt_limit_without_leaking_the_key_or_body(api):
    api.responses = [httpx.Response(429, text=f"quota exceeded for {SECRET}")] * embeddings.DOCUMENT_ATTEMPTS
    with pytest.raises(EmbeddingServiceError) as error:
        create_embeddings(["x"])
    assert SECRET not in str(error.value) and "quota" not in str(error.value)
    assert len(api.requests) == embeddings.DOCUMENT_ATTEMPTS


def test_a_user_waiting_on_a_query_only_gets_one_retry(api):
    api.responses = [httpx.Response(429)] * 5
    with pytest.raises(EmbeddingServiceError):
        create_query_embedding("question")
    assert len(api.requests) == embeddings.QUERY_ATTEMPTS


def test_client_errors_are_not_retried(api):
    api.responses = [httpx.Response(400, text="bad request")]
    with pytest.raises(EmbeddingServiceError, match="HTTP 400"):
        create_embeddings(["x"])
    assert len(api.requests) == 1 and api.sleeps == []


@pytest.mark.parametrize(
    "bad_response",
    [
        httpx.Response(200, json={"embeddings": []}),  # fewer vectors than texts
        httpx.Response(200, json={"embeddings": [{"values": [1.0, 2.0]}]}),  # wrong dimension
        httpx.Response(200, json={"embeddings": [{"values": [0.0] * EMBEDDING_DIMENSION}]}),  # zero vector
        httpx.Response(200, json={"unexpected": True}),
        httpx.Response(200, text="not json"),
    ],
)
def test_unusable_provider_responses_are_rejected(api, bad_response):
    api.responses = [bad_response]
    with pytest.raises(EmbeddingServiceError):
        create_embeddings(["x"])


def test_missing_key_and_empty_text_fail_before_any_request(api, monkeypatch):
    with pytest.raises(EmbeddingServiceError):
        create_embeddings(["valid", "   "])
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(EmbeddingServiceError, match="configuration"):
        create_embeddings(["x"])
    assert api.requests == []
