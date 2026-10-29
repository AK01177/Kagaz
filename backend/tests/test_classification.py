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


# ---------------------------------------------------------------------------
# QA-04 REGRESSION TESTS — coverage additions
# ---------------------------------------------------------------------------


# C. Missing confidence value
def test_classify_missing_confidence_defaults_to_1_0(monkeypatch):
    """When the provider omits the confidence field, the service defaults to 1.0.

    NOTE: Treating absent confidence as perfect confidence (1.0) is a known
    risk — a future sprint may want to default to a lower sentinel value such
    as 0.0. This test pins the *current documented behaviour* so any
    accidental change is caught immediately.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post_no_confidence(*args, **kwargs):
        # No "confidence" key in the flat response
        return MockResponse({"decision": "academics"})

    monkeypatch.setattr(httpx, "post", mock_post_no_confidence)

    result = classify_document("Student transcript GPA 4.0")
    assert result.category == DocumentCategory.ACADEMICS
    assert result.confidence == 1.0


def test_classify_missing_confidence_openrouter_format(monkeypatch):
    """Missing confidence in OpenRouter answers shape also defaults to 1.0."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post(*args, **kwargs):
        return MockResponse({
            "answers": {
                "category": {
                    "choice": "hr_documents",
                    # no "confidence" key, no "probabilities" key
                }
            }
        })

    monkeypatch.setattr(httpx, "post", mock_post)

    result = classify_document("Employee onboarding form")
    assert result.category == DocumentCategory.HR_DOCUMENTS
    assert result.confidence == 1.0


# D. API-key fallback environment variables
def test_classify_fallback_jev_api_key(monkeypatch):
    """JEV_API_KEY is accepted when OPENROUTER_API_KEY is absent."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("JEV_API_KEY", "jev_fake_key")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    def mock_post(*args, **kwargs):
        return MockResponse({"decision": "financial", "confidence": 0.88})

    monkeypatch.setattr(httpx, "post", mock_post)

    result = classify_document("Invoice payment due")
    assert result.category == DocumentCategory.FINANCIAL


def test_classify_fallback_typesafe_api_key(monkeypatch):
    """TYPESAFE_API_KEY is accepted when both OPENROUTER_API_KEY and JEV_API_KEY are absent."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "typesafe_fake_key")

    def mock_post(*args, **kwargs):
        return MockResponse({"decision": "general_confidential", "confidence": 0.75})

    monkeypatch.setattr(httpx, "post", mock_post)

    result = classify_document("Non-disclosure agreement")
    assert result.category == DocumentCategory.GENERAL_CONFIDENTIAL


# D. HTTP error status responses
def test_classify_http_4xx_error_raises_classification_error(monkeypatch):
    """A 4xx HTTP response (e.g. 401 Unauthorized) must raise ClassificationError."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "bad_key")

    def mock_post_401(*args, **kwargs):
        return MockResponse({"error": "Unauthorized"}, status_code=401)

    monkeypatch.setattr(httpx, "post", mock_post_401)

    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")


def test_classify_http_5xx_error_raises_classification_error(monkeypatch):
    """A 5xx HTTP response (e.g. 503 Service Unavailable) must raise ClassificationError."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post_503(*args, **kwargs):
        return MockResponse({"error": "Service Unavailable"}, status_code=503)

    monkeypatch.setattr(httpx, "post", mock_post_503)

    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")


# D. Non-dict / malformed provider response
def test_classify_non_dict_response_raises_classification_error(monkeypatch):
    """A provider that returns a JSON list instead of a dict must raise ClassificationError."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post_list(*args, **kwargs):
        # Override json() to return a list — simulates a completely wrong payload shape
        class _ListResponse:
            status_code = 200

            def json(self):
                return ["unexpected", "list", "payload"]

            def raise_for_status(self):
                pass

        return _ListResponse()

    monkeypatch.setattr(httpx, "post", mock_post_list)

    with pytest.raises(ClassificationError, match="Classification failed"):
        classify_document("Some text")


# B/C. Confidence resolution via probabilities path
def test_classify_confidence_from_probabilities_raw_decision_key(monkeypatch):
    """Confidence is taken from probabilities[raw_decision] when present."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post(*args, **kwargs):
        return MockResponse({
            "answers": {
                "category": {
                    "choice": "hr_documents",
                    "probabilities": {
                        "hr_documents": 0.87,
                        "financial": 0.08,
                        "academics": 0.03,
                        "general_confidential": 0.02,
                    },
                }
            }
        })

    monkeypatch.setattr(httpx, "post", mock_post)

    result = classify_document("Resume and cover letter")
    assert result.category == DocumentCategory.HR_DOCUMENTS
    assert result.confidence == 0.87


def test_classify_confidence_from_probabilities_resolved_category_key(monkeypatch):
    """Confidence falls back to probabilities[resolved_category] when raw decision key is absent."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def mock_post(*args, **kwargs):
        # The raw choice is an alias "transcript" which resolves to "academics".
        # probabilities keyed by resolved category name, not the alias.
        return MockResponse({
            "decision": "transcript",
            "probabilities": {
                "academics": 0.93,
                "financial": 0.04,
                "hr_documents": 0.02,
                "general_confidential": 0.01,
            },
        })

    monkeypatch.setattr(httpx, "post", mock_post)

    result = classify_document("University transcript for John Doe")
    assert result.category == DocumentCategory.ACADEMICS
    assert result.confidence == 0.93


# B. Additional alias categories
def test_classify_alias_academic_variants(monkeypatch):
    """Verify aliases 'diploma', 'marksheet', and 'exam' map to ACADEMICS."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    for alias in ("diploma", "marksheet", "exam"):
        def make_mock(a=alias):
            def _mock(*args, **kwargs):
                return MockResponse({"decision": a, "confidence": 0.80})
            return _mock

        monkeypatch.setattr(httpx, "post", make_mock())
        result = classify_document("Some academic text")
        assert result.category == DocumentCategory.ACADEMICS, (
            f"Alias '{alias}' should map to ACADEMICS, got {result.category}"
        )


def test_classify_alias_financial_variants(monkeypatch):
    """Verify aliases 'receipt', 'bank_statement', and 'tax_return' map to FINANCIAL."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    for alias in ("receipt", "bank_statement", "tax_return"):
        def make_mock(a=alias):
            def _mock(*args, **kwargs):
                return MockResponse({"decision": a, "confidence": 0.80})
            return _mock

        monkeypatch.setattr(httpx, "post", make_mock())
        result = classify_document("Some financial text")
        assert result.category == DocumentCategory.FINANCIAL, (
            f"Alias '{alias}' should map to FINANCIAL, got {result.category}"
        )


def test_classify_alias_general_confidential_variants(monkeypatch):
    """Verify aliases 'nda', 'passport', and 'policy' map to GENERAL_CONFIDENTIAL."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    for alias in ("nda", "passport", "policy"):
        def make_mock(a=alias):
            def _mock(*args, **kwargs):
                return MockResponse({"decision": a, "confidence": 0.80})
            return _mock

        monkeypatch.setattr(httpx, "post", make_mock())
        result = classify_document("Some confidential text")
        assert result.category == DocumentCategory.GENERAL_CONFIDENTIAL, (
            f"Alias '{alias}' should map to GENERAL_CONFIDENTIAL, got {result.category}"
        )


# B. Case normalization and hyphen-to-underscore conversion
def test_classify_category_case_insensitive(monkeypatch):
    """Category strings with mixed case or hyphens are normalized correctly."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    # Mixed-case canonical name
    def mock_upper(*args, **kwargs):
        return MockResponse({"decision": "FINANCIAL", "confidence": 0.90})

    monkeypatch.setattr(httpx, "post", mock_upper)
    result = classify_document("Invoice text")
    assert result.category == DocumentCategory.FINANCIAL

    # Hyphenated alias (HR_DOCUMENTS with a hyphen)
    def mock_hyphen(*args, **kwargs):
        return MockResponse({"decision": "hr-documents", "confidence": 0.90})

    monkeypatch.setattr(httpx, "post", mock_hyphen)
    result = classify_document("Resume text")
    assert result.category == DocumentCategory.HR_DOCUMENTS


# F. Manual correction / review flow — PATCH /api/documents/{id}/classification
# The `correct_classification` endpoint is implemented in api/documents.py.
# Tests below exercise it directly via the FastAPI TestClient (no real filesystem I/O,
# temp directories are used to avoid touching production storage_data/).

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def test_app_with_document(tmp_path, monkeypatch):
    """Provide a TestClient wired to a temp storage directory containing one document."""
    # Point DocumentStorage at a temp directory so tests are isolated
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))

    # Create the metadata subdirectory and seed a document metadata file
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    doc_id = "test-doc-001"
    initial_metadata = {
        "id": doc_id,
        "filename": "sample.pdf",
        "category": "financial",
        "confidence": 0.82,
        "status": "CLASSIFIED",
        "is_manually_corrected": False,
        "classification_history": [],
    }
    with open(metadata_dir / f"{doc_id}.json", "w") as f:
        json.dump(initial_metadata, f)

    from main import app
    client = TestClient(app)
    return client, doc_id


def test_manual_correction_valid_category(test_app_with_document):
    """PATCH with a valid corrected category must update metadata and return 200."""
    client, doc_id = test_app_with_document

    response = client.patch(
        f"/api/documents/{doc_id}/classification",
        json={"category": "academics", "notes": "Reviewer confirmed academic document"},
    )
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["category"] == "academics"
    assert data["confidence"] == 1.0
    assert data["is_manually_corrected"] is True
    assert data["status"] == "CLASSIFIED"


def test_manual_correction_persistence(test_app_with_document, tmp_path):
    """After correction, the metadata file on disk must reflect the change."""
    client, doc_id = test_app_with_document

    client.patch(
        f"/api/documents/{doc_id}/classification",
        json={"category": "hr_documents"},
    )

    metadata_path = tmp_path / "metadata" / f"{doc_id}.json"
    with open(metadata_path) as f:
        saved = json.load(f)

    assert saved["category"] == "hr_documents"
    assert saved["is_manually_corrected"] is True
    assert len(saved["classification_history"]) == 1
    assert saved["classification_history"][0]["previous_category"] == "financial"
    assert saved["classification_history"][0]["updated_category"] == "hr_documents"


def test_manual_correction_invalid_category(test_app_with_document):
    """PATCH with an unrecognized category must return 422 and an informative message."""
    client, doc_id = test_app_with_document

    response = client.patch(
        f"/api/documents/{doc_id}/classification",
        json={"category": "totally_wrong_category"},
    )
    assert response.status_code == 422
    # The error detail must name the offending value
    body = response.json()
    assert "totally_wrong_category" in str(body)


def test_manual_correction_document_not_found(test_app_with_document):
    """PATCH for a non-existent document_id must return 404."""
    client, _ = test_app_with_document

    response = client.patch(
        "/api/documents/nonexistent-doc-id/classification",
        json={"category": "financial"},
    )
    assert response.status_code == 404

# QA-02: Isolated backend unit tests


from services import classification


@pytest.mark.parametrize(
    "payload,expected",
    [
        (
            {"answers": {"category": {"choice": "invoice", "confidence": 0.8, "probabilities": {"invoice": 0.9}}}},
            ("invoice", 0.8, {"invoice": 0.9}),
        ),
        (
            {"decision": "hr_documents", "confidence": 0.75},
            ("hr_documents", 0.75, {}),
        ),
        (
            {"category": "financial", "probabilities": [0.4, 0.6]},
            ("financial", None, {}),
        ),
    ],
)
def test_decision_parser_handles_valid_provider_shapes(payload, expected):
    assert classification._extract_decision_fields(payload) == expected


@pytest.mark.parametrize("payload", [None, [], "invalid", 123])
def test_decision_parser_rejects_non_object_payload(payload):
    with pytest.raises(ValueError, match="Expected dict response"):
        classification._extract_decision_fields(payload)


@pytest.mark.parametrize(
    "resolved,raw,confidence,probabilities,expected",
    [
        ("financial", "invoice", 0.3, {"invoice": 0.8, "financial": 0.5}, 0.8),
        ("financial", "invoice", 0.3, {"financial": 0.7}, 0.7),
        ("financial", "invoice", 0.3, {"other": 0.7}, 0.3),
        ("financial", "invoice", 1.5, {}, 1.0),
        ("financial", "invoice", -0.2, {}, 0.0),
        ("financial", "invoice", "not-a-number", {}, 1.0),
        ("financial", "invoice", None, {}, 1.0),
    ],
)
def test_confidence_resolution_and_bounds(resolved, raw, confidence, probabilities, expected):
    result = classification._calculate_confidence(resolved, raw, confidence, probabilities)
    assert result == expected


def test_classification_normalizes_hyphenated_category(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-key")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"decision": "HR-Documents", "confidence": 0.82}

    monkeypatch.setattr(classification.httpx, "post", lambda *args, **kwargs: Response())

    result = classification.classify_document("Employee onboarding document")

    assert result.category == classification.DocumentCategory.HR_DOCUMENTS
    assert result.confidence == 0.82


@pytest.mark.parametrize("payload", [{"answers": {"category": {"choice": ""}}}, ["financial"], {}])
def test_classification_wraps_invalid_provider_responses(monkeypatch, payload):
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-key")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    monkeypatch.setattr(classification.httpx, "post", lambda *args, **kwargs: Response())

    with pytest.raises(classification.ClassificationError, match="Classification failed"):
        classification.classify_document("An invoice document")

