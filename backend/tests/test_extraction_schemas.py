"""
Unit tests for AI-05: Extraction Schemas, Per-Field Confidence, and Registry.
"""
import pytest
from pydantic import ValidationError

from app.schemas.extraction import (
    BaseDocumentExtraction,
    ExtractedField,
    ExtractionDocumentType,
    InvoiceExtraction,
    ResumeExtraction,
    get_extraction_schema,
    get_field_definitions,
    get_supported_extraction_types,
)


def test_schema_inheritance():
    """Verify that concrete extraction schemas inherit from BaseDocumentExtraction."""
    assert issubclass(InvoiceExtraction, BaseDocumentExtraction)
    assert issubclass(ResumeExtraction, BaseDocumentExtraction)


def test_extracted_field_default():
    """Verify default initialization of an empty extracted field."""
    field: ExtractedField[str] = ExtractedField()
    assert field.value is None
    assert field.confidence == 0.0
    assert field.raw_value is None
    assert field.is_present is False


def test_extracted_field_present_factory():
    """Verify convenience constructor for present fields."""
    field = ExtractedField.present(value="INV-2024-001", confidence=0.98, raw_value="Invoice #INV-2024-001")
    assert field.value == "INV-2024-001"
    assert field.confidence == 0.98
    assert field.raw_value == "Invoice #INV-2024-001"
    assert field.is_present is True


def test_extracted_field_missing_factory():
    """Verify convenience constructor for missing fields."""
    field = ExtractedField.missing()
    assert field.value is None
    assert field.confidence == 0.0
    assert field.raw_value is None
    assert field.is_present is False


def test_extracted_field_confidence_bounds():
    """Ensure confidence strictly validates within [0.0, 1.0]."""
    # Valid boundaries
    f_zero = ExtractedField(value="test", confidence=0.0)
    assert f_zero.confidence == 0.0

    f_one = ExtractedField(value="test", confidence=1.0)
    assert f_one.confidence == 1.0

    # Below 0.0
    with pytest.raises(ValidationError):
        ExtractedField(value="test", confidence=-0.1)

    # Above 1.0
    with pytest.raises(ValidationError):
        ExtractedField(value="test", confidence=1.05)


def test_invoice_extraction_defaults():
    """Verify invoice extraction schema initializes empty with all required fields missing."""
    invoice = InvoiceExtraction()
    assert invoice.invoice_number.value is None
    assert invoice.invoice_date.value is None
    assert invoice.supplier_name.value is None
    assert invoice.total_amount.value is None
    assert invoice.average_confidence() == 0.0
    assert set(invoice.get_missing_fields()) == {
        "invoice_number", "invoice_date", "supplier_name", "total_amount"
    }


def test_invoice_extraction_populated():
    """Verify invoice extraction correctly handles populated values, confidences, and dict export."""
    invoice = InvoiceExtraction(
        invoice_number=ExtractedField.present("INV-9821", confidence=0.95),
        invoice_date=ExtractedField.present("2024-10-15", confidence=0.90),
        supplier_name=ExtractedField.present("ACME Corp", confidence=0.99),
        total_amount=ExtractedField.present(450.00, confidence=0.92, raw_value="$450.00"),
    )

    flat = invoice.to_flat_dict()
    assert flat["invoice_number"] == "INV-9821"
    assert flat["invoice_date"] == "2024-10-15"
    assert flat["supplier_name"] == "ACME Corp"
    assert flat["total_amount"] == 450.00

    confidences = invoice.get_field_confidences()
    assert confidences["invoice_number"] == 0.95
    assert confidences["total_amount"] == 0.92

    assert invoice.get_missing_fields() == []
    assert invoice.average_confidence() == round((0.95 + 0.90 + 0.99 + 0.92) / 4, 4)


def test_invoice_partial_extraction():
    """Verify handling when some invoice fields are missing."""
    invoice = InvoiceExtraction(
        invoice_number=ExtractedField.present("INV-9821", confidence=0.95),
        total_amount=ExtractedField.present(450.00, confidence=0.90),
    )
    missing = invoice.get_missing_fields()
    assert "invoice_date" in missing
    assert "supplier_name" in missing
    assert "invoice_number" not in missing
    assert "total_amount" not in missing


def test_resume_extraction():
    """Verify resume extraction schema with list fields (skills) and contact info."""
    resume = ResumeExtraction(
        candidate_name=ExtractedField.present("John Doe", confidence=0.97),
        email=ExtractedField.present("john.doe@example.com", confidence=0.99),
        phone=ExtractedField.present("+1-555-0199", confidence=0.88),
        skills=ExtractedField.present(["Python", "FastAPI", "React"], confidence=0.94),
    )

    flat = resume.to_flat_dict()
    assert flat["candidate_name"] == "John Doe"
    assert flat["email"] == "john.doe@example.com"
    assert flat["phone"] == "+1-555-0199"
    assert flat["skills"] == ["Python", "FastAPI", "React"]

    assert resume.get_missing_fields() == []
    assert resume.average_confidence() == round((0.97 + 0.99 + 0.88 + 0.94) / 4, 4)


def test_get_extraction_schema_resolution():
    """Verify registry resolves known types, enums, and handles case/whitespace insensitivity."""
    assert get_extraction_schema("invoice") is InvoiceExtraction
    assert get_extraction_schema("INVOICE") is InvoiceExtraction
    assert get_extraction_schema("  invoice  ") is InvoiceExtraction
    assert get_extraction_schema(ExtractionDocumentType.INVOICE) is InvoiceExtraction

    assert get_extraction_schema("resume") is ResumeExtraction
    assert get_extraction_schema("hr_form") is ResumeExtraction
    assert get_extraction_schema(ExtractionDocumentType.RESUME) is ResumeExtraction

    # Unsupported or invalid types
    assert get_extraction_schema("unsupported_type") is None
    assert get_extraction_schema("") is None
    assert get_extraction_schema(None) is None


def test_get_supported_extraction_types():
    """Verify list of supported types matches expected registry keys."""
    supported = get_supported_extraction_types()
    assert "invoice" in supported
    assert "resume" in supported
    assert "hr_form" in supported


def test_get_field_definitions():
    """Verify field definitions return correct metadata for schemas."""
    invoice_fields = get_field_definitions("invoice")
    assert "invoice_number" in invoice_fields
    assert "total_amount" in invoice_fields
    assert "supplier_name" in invoice_fields
    assert "invoice_date" in invoice_fields
    assert "description" in invoice_fields["invoice_number"]

    resume_fields = get_field_definitions("resume")
    assert "candidate_name" in resume_fields
    assert "skills" in resume_fields
    assert "email" in resume_fields
    assert "phone" in resume_fields

    unknown_fields = get_field_definitions("non_existent")
    assert unknown_fields == {}
