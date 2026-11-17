"""Policies and documents meet on the classifier's four categories (RAG Phase 3)."""
import pytest

from services.classification import DocumentCategory
from services.document_types import (
    CANONICAL_DOCUMENT_TYPES,
    canonical_document_type,
    document_type_spellings,
    require_document_type,
)


def test_the_types_are_exactly_the_classifiers_categories_and_nothing_new():
    assert set(CANONICAL_DOCUMENT_TYPES) == {category.value for category in DocumentCategory}
    assert len(CANONICAL_DOCUMENT_TYPES) == 4


@pytest.mark.parametrize(
    ("spelling", "expected"),
    [
        ("financial", "financial"),
        ("FINANCIAL", "financial"),
        ("Invoice", "financial"),
        ("  invoice  ", "financial"),
        ("Invoices", "financial"),
        ("Expense Claim", "financial"),
        ("purchase-order", "financial"),
        ("HR", "hr_documents"),
        ("hr-documents", "hr_documents"),
        ("HR Documents", "hr_documents"),
        ("HR Forms", "hr_documents"),
        ("Resume", "hr_documents"),
        ("academics", "academics"),  # ends in "s" but is already canonical
        ("Academic Records", "academics"),
        ("Transcript", "academics"),
        ("General with Confidentiality", "general_confidential"),
        ("contract", "general_confidential"),
    ],
)
def test_every_spelling_resolves_to_one_category(spelling, expected):
    assert canonical_document_type(spelling) == expected


@pytest.mark.parametrize("unknown", ["memo", "bus", "   ", "", None])
def test_unknown_or_blank_values_have_no_category(unknown):
    assert canonical_document_type(unknown) is None


def test_spellings_include_the_canonical_value_and_every_alias_of_it():
    spellings = document_type_spellings("Invoice")
    assert {"financial", "invoice", "expense_claim", "purchase_order"} <= spellings
    assert document_type_spellings("hr") == document_type_spellings("hr_documents")
    assert "invoice" not in document_type_spellings("transcript")


def test_an_unknown_type_only_matches_itself_and_blank_means_no_filter():
    assert document_type_spellings("Memo") == {"memo"}
    assert document_type_spellings("  ") == set() and document_type_spellings(None) == set()


def test_saving_a_policy_stores_the_canonical_type_or_none():
    assert require_document_type("Invoice") == "financial"
    assert require_document_type("  ") is None and require_document_type(None) is None


def test_saving_a_policy_with_an_unknown_type_is_rejected_with_the_valid_choices():
    with pytest.raises(ValueError) as error:
        require_document_type("memo")
    message = str(error.value)
    assert "memo" in message and all(name in message for name in CANONICAL_DOCUMENT_TYPES)
