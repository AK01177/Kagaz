"""What "document type" means for policies: the classifier's own categories, nothing new.

A document is classified into one of the four `DocumentCategory` values, always stored in
lower case. A policy says which category it applies to, but people type that in many
spellings ("Invoice", "HR", "hr-documents", "Transcript"). Every spelling is resolved through
the classifier's alias table (`CATEGORY_ALIASES`), so a policy and a document meet on the
same canonical value no matter how either was written.
"""
from __future__ import annotations

from services.classification import CATEGORY_ALIASES, DocumentCategory

CANONICAL_DOCUMENT_TYPES: tuple[str, ...] = tuple(category.value for category in DocumentCategory)


def _lookup_keys(value: str) -> list[str]:
    """Spellings to try, mirroring how the classifier normalises its own output.

    Exact spellings come first so "academics" stays itself; a plural ("Invoices",
    "HR Forms") is only tried as its singular when nothing matched.
    """
    key = " ".join(value.strip().lower().replace("-", "_").split())
    underscored = key.replace(" ", "_")
    keys = [key, underscored]
    if underscored.endswith("s"):
        keys.append(underscored[:-1])
    return keys


def canonical_document_type(value: str | None) -> str | None:
    """The category a spelling stands for, or None when blank or not a known spelling."""
    if not value or not value.strip():
        return None
    for key in _lookup_keys(value):
        if key in CANONICAL_DOCUMENT_TYPES:
            return key
        if key in CATEGORY_ALIASES:
            return CATEGORY_ALIASES[key]
    return None


def document_type_spellings(value: str | None) -> set[str]:
    """Every normalised spelling that means the same type as `value`; empty when no type is given.

    Used to match policies stored with any spelling, including data written before
    normalisation existed. An unknown value only matches itself.
    """
    if not value or not value.strip():
        return set()
    canonical = canonical_document_type(value)
    if canonical is None:
        return {_lookup_keys(value)[0]}
    aliases = {alias for alias, target in CATEGORY_ALIASES.items() if target == canonical}
    return aliases | {canonical}


def require_document_type(value: str | None) -> str | None:
    """Canonical type for a policy being saved; None means "applies to every document type".

    An unknown value is rejected: it could never match a classified document, so the policy
    would silently never apply.
    """
    if value is None or not value.strip():
        return None
    canonical = canonical_document_type(value)
    if canonical is None:
        raise ValueError(
            f"Unknown document type '{value.strip()}'. Use one of: {', '.join(CANONICAL_DOCUMENT_TYPES)} "
            "(common spellings such as 'invoice' or 'HR' are accepted), or leave it empty for every type."
        )
    return canonical
