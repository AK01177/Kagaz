"""
Unit tests for AI-06: Structured Extraction Service.
Verifies parsing, type validation, missing field handling, and error safety.
"""
import json
import httpx
import pytest

from app.schemas.extraction import (
    InvoiceExtraction,
    ResumeExtraction,
)
from services.structured_extraction import (
    StructuredExtractionError,
    UnsupportedDocumentTypeError,
    extract_structured_fields,
    parse_and_validate_fields,
    _sanitize_field_value,
)


def _mock_completion_payload(content_dict_or_str):
    content = (
        json.dumps(content_dict_or_str)
        if isinstance(content_dict_or_str, (dict, list))
        else str(content_dict_or_str)
    )
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }


def test_extract_invoice_structured_success(monkeypatch):
    """Verify full structured invoice extraction with typed fields and confidences."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    mock_invoice_data = {
        "invoice_number": {
            "value": "INV-2024-9821",
            "confidence": 0.98,
            "raw_value": "Invoice #INV-2024-9821",
        },
        "invoice_date": {
            "value": "2024-10-15",
            "confidence": 0.91,
            "raw_value": "Date: Oct 15, 2024",
        },
        "supplier_name": {
            "value": "ACME Supplies Inc.",
            "confidence": 0.99,
            "raw_value": "ACME Supplies Inc.",
        },
        "total_amount": {
            "value": 450.50,
            "confidence": 0.94,
            "raw_value": "$450.50",
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_mock_completion_payload(mock_invoice_data))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = extract_structured_fields(
        text="Sample invoice text",
        document_type="invoice",
        client=client,
    )

    assert isinstance(result, InvoiceExtraction)
    assert result.invoice_number.value == "INV-2024-9821"
    assert result.invoice_number.confidence == 0.98
    assert result.invoice_number.is_present is True
    assert result.total_amount.value == 450.50
    assert result.supplier_name.value == "ACME Supplies Inc."
    assert result.get_missing_fields() == []


def test_extract_flat_fields_and_currency_coercion(monkeypatch):
    """Verify that flat JSON outputs and currency strings like '$1,250.00' are parsed and sanitized."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    mock_flat_data = {
        "invoice_number": "INV-1001",
        "invoice_date": "2024-11-01",
        "supplier_name": "Target",
        "total_amount": "$1,250.00",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_mock_completion_payload(mock_flat_data))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = extract_structured_fields("Invoice text", "invoice", client=client)

    assert result.invoice_number.value == "INV-1001"
    assert result.total_amount.value == 1250.00
    assert result.total_amount.is_present is True


def test_extract_resume_with_skills_list(monkeypatch):
    """Verify resume extraction properly handles candidate info and skills lists."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    mock_resume_data = {
        "candidate_name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1-555-0199",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_mock_completion_payload(mock_resume_data))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = extract_structured_fields("Resume text", "resume", client=client)

    assert isinstance(result, ResumeExtraction)
    assert result.candidate_name.value == "John Doe"
    assert result.skills.value == ["Python", "FastAPI", "PostgreSQL"]
    assert result.skills.is_present is True


def test_missing_fields_represented_consistently():
    """Verify that absent or null fields are represented consistently with 0.0 confidence."""
    raw_data = {
        "invoice_number": "INV-102",
        "supplier_name": None,
    }
    result = parse_and_validate_fields(raw_data, InvoiceExtraction)

    assert result.invoice_number.is_present is True
    assert result.invoice_number.value == "INV-102"

    assert result.supplier_name.is_present is False
    assert result.supplier_name.value is None
    assert result.supplier_name.confidence == 0.0

    assert result.total_amount.is_present is False
    assert result.total_amount.value is None
    assert result.total_amount.confidence == 0.0


def test_extract_empty_text_error():
    """Verify passing empty or whitespace text raises StructuredExtractionError."""
    with pytest.raises(StructuredExtractionError, match="empty or missing"):
        extract_structured_fields("", "invoice")
    with pytest.raises(StructuredExtractionError, match="empty or missing"):
        extract_structured_fields("   \n\t  ", "invoice")


def test_extract_unsupported_document_type():
    """Verify passing an unsupported document type raises UnsupportedDocumentTypeError."""
    with pytest.raises(UnsupportedDocumentTypeError, match="No extraction schema registered"):
        extract_structured_fields("Some text", "unsupported_doc_type")


def test_extract_missing_api_key(monkeypatch):
    """Verify error raised when no API key is provided or present in environment."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(StructuredExtractionError, match="OPENROUTER_API_KEY environment variable is not set"):
        extract_structured_fields("Some text", "invoice")


def test_extract_markdown_wrapped_json(monkeypatch):
    """Verify model responses with markdown ```json ... ``` code blocks are parsed cleanly."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    wrapped_content = "```json\n{\"invoice_number\": \"INV-999\", \"total_amount\": 88.0}\n```"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_mock_completion_payload(wrapped_content))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = extract_structured_fields("Some text", "invoice", client=client)

    assert result.invoice_number.value == "INV-999"
    assert result.total_amount.value == 88.0


def test_extract_invalid_json_handling(monkeypatch):
    """Verify that malformed/non-JSON model responses raise StructuredExtractionError."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_mock_completion_payload("Not JSON content at all"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(StructuredExtractionError, match="Structured extraction failed"):
        extract_structured_fields("Some text", "invoice", client=client)


def test_sanitize_field_values_helpers():
    """Unit test individual value sanitization helpers for amounts and skills."""
    # Currency conversions
    assert _sanitize_field_value("total_amount", "$500.00") == 500.0
    assert _sanitize_field_value("total_amount", "€1,200.50") == 1200.50
    assert _sanitize_field_value("total_amount", "invalid") is None

    # Skills conversions from string to list
    assert _sanitize_field_value("skills", "Python, Docker, SQL") == ["Python", "Docker", "SQL"]
    assert _sanitize_field_value("skills", ["React", "TypeScript"]) == ["React", "TypeScript"]


def test_invalid_field_type_is_handled_safely():
    """Invalid amount values should become missing fields."""
    result = parse_and_validate_fields(
        {"total_amount": "not-a-number"},
        InvoiceExtraction,
    )

    assert result.total_amount.value is None
    assert result.total_amount.is_present is False
    assert result.total_amount.confidence == 0.0


def test_low_confidence_is_preserved():
    """Low model confidence should be preserved, not raised artificially."""
    result = parse_and_validate_fields(
        {
            "invoice_number": {
                "value": "INV-LOW",
                "confidence": 0.1,
                "raw_value": "INV-LOW",
            }
        },
        InvoiceExtraction,
    )

    assert result.invoice_number.value == "INV-LOW"
    assert result.invoice_number.is_present is True
    assert result.invoice_number.confidence == 0.1


def test_provider_http_failure_is_wrapped(monkeypatch):
    """An HTTP error from the provider should become a structured extraction error."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        with pytest.raises(StructuredExtractionError):
            extract_structured_fields(
                text="Invoice text",
                document_type="invoice",
                client=client,
            )
    finally:
        client.close()


def test_invalid_provider_response_structure_is_wrapped(monkeypatch):
    """A response without completion choices should raise a safe extraction error."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake_key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "response"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        with pytest.raises(StructuredExtractionError):
            extract_structured_fields(
                text="Invoice text",
                document_type="invoice",
                client=client,
            )
    finally:
        client.close()
