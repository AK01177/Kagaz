import httpx
import pytest
from services.classification import ClassificationError, DocumentCategory, classify_document


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=None, response=self)


def test_classify_empty_text():
    """Test that passing empty strings or whitespace raises an error immediately."""
    with pytest.raises(ClassificationError, match="empty or missing"):
        classify_document("")
    with pytest.raises(ClassificationError, match="empty or missing"):
        classify_document("   \n\t  ")


def test_classify_no_api_key(monkeypatch):
    """Test that missing API keys raises an error."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(ClassificationError, match="OPENROUTER_API_KEY environment variable is not set"):
        classify_document("Some text")


def test_classify_4_canonical_domains(monkeypatch):
    """Verify that classification maps into the 4 canonical domains: academics, hr_documents, financial, general_confidential."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    # 1. Financial
    def mock_financial(*args, **kwargs):
        return MockResponse({"decision": "financial", "confidence": 0.96})
    monkeypatch.setattr(httpx, "post", mock_financial)
    res_fin = classify_document("Invoice $500")
    assert res_fin.category == DocumentCategory.FINANCIAL
    assert res_fin.category.value == "financial"

    # 2. HR Documents
    def mock_hr(*args, **kwargs):
        return MockResponse({"decision": "hr_documents", "confidence": 0.94})
    monkeypatch.setattr(httpx, "post", mock_hr)
    res_hr = classify_document("Resume John Doe")
    assert res_hr.category == DocumentCategory.HR_DOCUMENTS
    assert res_hr.category.value == "hr_documents"

    # 3. Academics
    def mock_acad(*args, **kwargs):
        return MockResponse({"decision": "academics", "confidence": 0.98})
    monkeypatch.setattr(httpx, "post", mock_acad)
    res_acad = classify_document("Transcript GPA 3.9")
    assert res_acad.category == DocumentCategory.ACADEMICS
    assert res_acad.category.value == "academics"

    # 4. General with confidentiality
    def mock_gen(*args, **kwargs):
        return MockResponse({"decision": "general_confidential", "confidence": 0.91})
    monkeypatch.setattr(httpx, "post", mock_gen)
    res_gen = classify_document("Non-Disclosure Agreement")
    assert res_gen.category == DocumentCategory.GENERAL_CONFIDENTIAL
    assert res_gen.category.value == "general_confidential"


def test_classify_success_openrouter_format(monkeypatch):
    """Test classification with OpenRouter decisions response format."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post(*args, **kwargs):
        return MockResponse({
            "answers": {
                "category": {
                    "choice": "financial",
                    "confidence": 0.95,
                    "probabilities": {"financial": 0.95, "general_confidential": 0.05},
                }
            }
        })
    monkeypatch.setattr(httpx, "post", mock_post)

    result = classify_document("Some invoice text here")
    assert result.category == DocumentCategory.FINANCIAL
    assert result.confidence == 0.95


def test_classify_category_alias_mapping(monkeypatch):
    """Test that common synonyms like 'resume', 'invoice', 'contract' normalize into the 4 canonical categories."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    # Resume -> hr_documents
    def mock_resume(*args, **kwargs):
        return MockResponse({"decision": "resume", "confidence": 0.92})
    monkeypatch.setattr(httpx, "post", mock_resume)
    assert classify_document("Resume text").category == DocumentCategory.HR_DOCUMENTS

    # Invoice -> financial
    def mock_invoice(*args, **kwargs):
        return MockResponse({"decision": "invoice", "confidence": 0.95})
    monkeypatch.setattr(httpx, "post", mock_invoice)
    assert classify_document("Invoice text").category == DocumentCategory.FINANCIAL

    # Contract -> general_confidential
    def mock_contract(*args, **kwargs):
        return MockResponse({"decision": "contract", "confidence": 0.88})
    monkeypatch.setattr(httpx, "post", mock_contract)
    assert classify_document("Contract text").category == DocumentCategory.GENERAL_CONFIDENTIAL


def test_classify_api_network_failure(monkeypatch):
    """Test that network exceptions are properly caught and wrapped in ClassificationError."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post_fail(*args, **kwargs):
        raise httpx.RequestError("Network timeout connecting to Jev")
    monkeypatch.setattr(httpx, "post", mock_post_fail)

    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")


def test_classify_text_truncation(monkeypatch):
    """Test that extremely long text is safely truncated to 10,000 characters before sending."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post_check_length(*args, **kwargs):
        json_payload = kwargs.get("json", {})
        doc_text = json_payload.get("state", {}).get("document_text", "")
        assert len(doc_text) == 10000
        return MockResponse({"decision": "financial", "confidence": 0.95})
    monkeypatch.setattr(httpx, "post", mock_post_check_length)

    long_text = "A" * 15000
    classify_document(long_text)


def test_classify_unrecognized_category_fallback(monkeypatch):
    """Test when the API returns an unknown category, it safely maps to general_confidential."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post_unknown(*args, **kwargs):
        return MockResponse({"decision": "unknown_future_doc_type", "confidence": 0.60})
    monkeypatch.setattr(httpx, "post", mock_post_unknown)

    result = classify_document("Some text")
    assert result.category == DocumentCategory.GENERAL_CONFIDENTIAL
    assert result.confidence == 0.60


def test_classify_confidence_clamping(monkeypatch):
    """Test that out-of-bounds confidence values are clamped safely between 0.0 and 1.0."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post_high_conf(*args, **kwargs):
        return MockResponse({"decision": "financial", "confidence": 1.5})
    monkeypatch.setattr(httpx, "post", mock_post_high_conf)

    result = classify_document("Some text")
    assert result.confidence == 1.0

    def mock_post_neg_conf(*args, **kwargs):
        return MockResponse({"decision": "financial", "confidence": -0.2})
    monkeypatch.setattr(httpx, "post", mock_post_neg_conf)

    result_neg = classify_document("Some text")
    assert result_neg.confidence == 0.0


def test_classify_missing_decision_choice(monkeypatch):
    """Test when the API response has no decision choice, it raises ClassificationError."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post_empty(*args, **kwargs):
        return MockResponse({"answers": {}})
    monkeypatch.setattr(httpx, "post", mock_post_empty)

    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")
