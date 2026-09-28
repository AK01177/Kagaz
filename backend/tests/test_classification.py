import pytest
from services.classification import classify_document, DocumentCategory, ClassificationError

# --- Mock Classes to simulate Jev SDK (typesafe_sdk) ---

class MockChoice:
    def __init__(self, choice, confidence):
        self.choice = choice
        self.confidence = confidence

class MockChoices:
    def __init__(self, category_choice, category_prob):
        self._category = MockChoice(category_choice, category_prob)
        
    def __getitem__(self, key):
        if key == "category":
            return self._category
        raise KeyError(key)

class MockResult:
    def __init__(self, category_choice="invoice", category_prob=0.95):
        self.choices = MockChoices(category_choice, category_prob)

class MockTypeSafeClientSuccess:
    def __init__(self, api_key=None, base_url=None):
        pass
        
    def system_one(self, state, questions, model):
        assert model == "typesafe/jev-1.13"
        return MockResult()

class MockTypeSafeClientDifferentCategory:
    def __init__(self, api_key=None, base_url=None):
        pass
        
    def system_one(self, state, questions, model):
        return MockResult(category_choice="contract", category_prob=0.88)

class MockTypeSafeClientFailure:
    def __init__(self, api_key=None, base_url=None):
        pass
        
    def system_one(self, state, questions, model):
        raise ValueError("Network timeout connecting to Jev")

# --- Test Cases ---

def test_classify_empty_text():
    """Test that passing empty strings or whitespace raises an error immediately."""
    with pytest.raises(ClassificationError, match="empty or missing"):
        classify_document("")

def test_classify_no_api_key(monkeypatch):
    """Test that missing API key raises an error."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ClassificationError, match="OPENROUTER_API_KEY environment variable is not set"):
        classify_document("Some text")

def test_classify_success_invoice(monkeypatch):
    """Test that a standard successful classification returns the correct category."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")
    monkeypatch.setattr("services.classification.TypeSafeClient", MockTypeSafeClientSuccess)
    
    result = classify_document("Some invoice text here")
    assert result.category == DocumentCategory.INVOICE
    assert result.confidence == 0.95

def test_classify_success_contract(monkeypatch):
    """Test that different categories are handled correctly."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")
    monkeypatch.setattr("services.classification.TypeSafeClient", MockTypeSafeClientDifferentCategory)
    
    result = classify_document("Some contract text here")
    assert result.category == DocumentCategory.CONTRACT
    assert result.confidence == 0.88

def test_classify_api_failure(monkeypatch):
    """Test that underlying SDK exceptions are properly caught and wrapped."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")
    monkeypatch.setattr("services.classification.TypeSafeClient", MockTypeSafeClientFailure)
    
    with pytest.raises(ClassificationError, match="Classification failed: Network timeout"):
        classify_document("Some text")

def test_classify_text_truncation(monkeypatch):
    """Test that extremely long text is safely truncated before sending to Jev."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")
    
    class MockClientCheckLength:
        def __init__(self, api_key=None, base_url=None):
            pass
            
        def system_one(self, state, questions, model):
            # Assert that the text was properly truncated to 10,000 characters
            assert len(state) == 10000
            return MockResult()
            
    monkeypatch.setattr("services.classification.TypeSafeClient", MockClientCheckLength)
    
    long_text = "A" * 15000
    classify_document(long_text)

def test_classify_invalid_category_from_sdk(monkeypatch):
    """Test when the SDK returns a category we don't recognize. Pydantic should catch it."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")
    
    class MockClientInvalidCategory:
        def __init__(self, api_key=None, base_url=None):
            pass
            
        def system_one(self, state, questions, model):
            return MockResult(category_choice="weird_unsupported_category", category_prob=0.99)
            
    monkeypatch.setattr("services.classification.TypeSafeClient", MockClientInvalidCategory)
    
    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")

def test_classify_invalid_confidence_from_sdk(monkeypatch):
    """Test when the SDK returns an out-of-bounds confidence. Pydantic should catch it."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")
    
    class MockClientInvalidConfidence:
        def __init__(self, api_key=None, base_url=None):
            pass
            
        def system_one(self, state, questions, model):
            # Confidence should be between 0.0 and 1.0, 1.5 is invalid
            return MockResult(category_choice="invoice", category_prob=1.5)
            
    monkeypatch.setattr("services.classification.TypeSafeClient", MockClientInvalidConfidence)
    
    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")
