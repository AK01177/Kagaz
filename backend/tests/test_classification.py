import pytest
import httpx
from services.classification import classify_document, DocumentCategory, ClassificationError

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

def test_classify_no_api_key(monkeypatch):
    """Test that missing API key raises an error."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(ClassificationError, match="TYPESAFE_API_KEY environment variable is not set"):
        classify_document("Some text")

def test_classify_success_invoice(monkeypatch):
    """Test that a standard successful classification returns the correct category."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake_key")
    
    def mock_post(*args, **kwargs):
        return MockResponse({"decision": "invoice", "confidence": 0.95})
    monkeypatch.setattr(httpx, "post", mock_post)
    
    result = classify_document("Some invoice text here")
    assert result.category == DocumentCategory.INVOICE
    assert result.confidence == 0.95

def test_classify_success_contract(monkeypatch):
    """Test that different categories are handled correctly."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake_key")
    
    def mock_post(*args, **kwargs):
        return MockResponse({"category": "contract", "confidence": 0.88})
    monkeypatch.setattr(httpx, "post", mock_post)
    
    result = classify_document("Some contract text here")
    assert result.category == DocumentCategory.CONTRACT
    assert result.confidence == 0.88

def test_classify_api_failure(monkeypatch):
    """Test that underlying HTTP exceptions are properly caught and wrapped."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake_key")
    
    def mock_post_fail(*args, **kwargs):
        raise httpx.RequestError("Network timeout connecting to Jev")
    monkeypatch.setattr(httpx, "post", mock_post_fail)
    
    with pytest.raises(ClassificationError, match="Classification failed: Network timeout"):
        classify_document("Some text")

def test_classify_text_truncation(monkeypatch):
    """Test that extremely long text is safely truncated before sending to API."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake_key")
    
    def mock_post_check_length(*args, **kwargs):
        json_payload = kwargs.get("json", {})
        context = json_payload.get("input", {}).get("context", "")
        assert len(context) == 10000
        return MockResponse({"decision": "invoice", "confidence": 0.95})
    monkeypatch.setattr(httpx, "post", mock_post_check_length)
    
    long_text = "A" * 15000
    classify_document(long_text)

def test_classify_invalid_category_from_api(monkeypatch):
    """Test when the API returns a category we don't recognize."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake_key")
    
    def mock_post_invalid_cat(*args, **kwargs):
        return MockResponse({"decision": "weird_unsupported_category", "confidence": 0.99})
    monkeypatch.setattr(httpx, "post", mock_post_invalid_cat)
    
    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")

def test_classify_invalid_confidence_from_api(monkeypatch):
    """Test when the API returns an out-of-bounds confidence."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake_key")
    
    def mock_post_invalid_conf(*args, **kwargs):
        return MockResponse({"decision": "invoice", "confidence": 1.5})
    monkeypatch.setattr(httpx, "post", mock_post_invalid_conf)
    
    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")
