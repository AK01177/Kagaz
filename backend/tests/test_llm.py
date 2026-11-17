"""Chat client: JSON parsing, retries and secrecy (RAG Phase 4/5)."""
import httpx
import pytest

from services import gemini_http, llm
from services.llm import LLMServiceError, chat_json

SECRET = "AIza-test-secret-key"


class FakeApi:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.requests.append({"url": url, "json": json, "headers": headers})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def completion(content) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    fake = FakeApi()
    sleeps = []
    monkeypatch.setattr(gemini_http.httpx, "post", fake)
    monkeypatch.setattr(gemini_http, "_sleep", sleeps.append)
    fake.sleeps = sleeps
    return fake


def test_a_json_answer_is_parsed_and_the_request_is_deterministic_json_mode(api):
    api.responses = [completion('{"answer": "12 days"}')]
    assert chat_json("system text", "user text") == {"answer": "12 days"}
    sent = api.requests[0]
    assert sent["json"]["temperature"] == 0 and sent["json"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in sent["json"]["messages"]] == ["system", "user"]
    assert sent["headers"]["Authorization"] == f"Bearer {SECRET}" and SECRET not in sent["url"]


def test_a_markdown_code_fence_around_the_json_is_tolerated(api):
    api.responses = [completion('```json\n{"ok": true}\n```')]
    assert chat_json("s", "u") == {"ok": True}


@pytest.mark.parametrize(
    "bad",
    [completion("not json"), completion("[1, 2]"), completion(None), httpx.Response(200, json={"choices": []}), httpx.Response(200, text="oops")],
)
def test_unusable_output_is_reported_as_an_error(api, bad):
    api.responses = [bad]
    with pytest.raises(LLMServiceError):
        chat_json("s", "u")


def test_rate_limits_and_outages_are_retried_then_given_up_without_leaking_details(api):
    api.responses = [httpx.Response(429, headers={"retry-after": "3"}), httpx.ConnectTimeout("t"), completion('{"ok": 1}')]
    assert chat_json("s", "u") == {"ok": 1}
    assert api.sleeps == [3.0, 4.0]

    api.responses = [httpx.Response(503, text=f"overloaded {SECRET}")] * llm.ATTEMPTS
    with pytest.raises(LLMServiceError) as error:
        chat_json("s", "u")
    assert SECRET not in str(error.value) and "overloaded" not in str(error.value)


def test_a_missing_key_fails_before_any_request(api, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    assert not llm.llm_is_configured()
    with pytest.raises(LLMServiceError, match="configuration"):
        chat_json("s", "u")
    assert api.requests == []
