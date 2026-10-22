import enum
import os
from typing import Any, Dict, Optional
import httpx
from pydantic import BaseModel, Field


# 4 Target Classification Domains
class DocumentCategory(str, enum.Enum):
    ACADEMICS = "academics"
    HR_DOCUMENTS = "hr_documents"
    FINANCIAL = "financial"
    GENERAL_CONFIDENTIAL = "general_confidential"


# Backwards compatibility enum aliases for older references
DocumentCategory.INVOICE = DocumentCategory.FINANCIAL  # type: ignore[attr-defined]
DocumentCategory.FINANCIAL_REPORT = DocumentCategory.FINANCIAL  # type: ignore[attr-defined]
DocumentCategory.HR_FORM = DocumentCategory.HR_DOCUMENTS  # type: ignore[attr-defined]
DocumentCategory.ACADEMIC_RECORD = DocumentCategory.ACADEMICS  # type: ignore[attr-defined]
DocumentCategory.CONTRACT = DocumentCategory.GENERAL_CONFIDENTIAL  # type: ignore[attr-defined]
DocumentCategory.IDENTITY_DOCUMENT = DocumentCategory.GENERAL_CONFIDENTIAL  # type: ignore[attr-defined]
DocumentCategory.POLICY_DOCUMENT = DocumentCategory.GENERAL_CONFIDENTIAL  # type: ignore[attr-defined]
DocumentCategory.OTHER = DocumentCategory.GENERAL_CONFIDENTIAL  # type: ignore[attr-defined]


# Common aliases and synonyms mapping into the 4 canonical categories
CATEGORY_ALIASES: Dict[str, str] = {
    # 1. Academics
    "academics": DocumentCategory.ACADEMICS.value,
    "academic": DocumentCategory.ACADEMICS.value,
    "academic_record": DocumentCategory.ACADEMICS.value,
    "transcript": DocumentCategory.ACADEMICS.value,
    "diploma": DocumentCategory.ACADEMICS.value,
    "degree": DocumentCategory.ACADEMICS.value,
    "certificate": DocumentCategory.ACADEMICS.value,
    "marksheet": DocumentCategory.ACADEMICS.value,
    "syllabus": DocumentCategory.ACADEMICS.value,
    "coursework": DocumentCategory.ACADEMICS.value,
    "assignment": DocumentCategory.ACADEMICS.value,
    "exam": DocumentCategory.ACADEMICS.value,

    # 2. HR Documents
    "hr_documents": DocumentCategory.HR_DOCUMENTS.value,
    "hr_document": DocumentCategory.HR_DOCUMENTS.value,
    "hr_form": DocumentCategory.HR_DOCUMENTS.value,
    "hr": DocumentCategory.HR_DOCUMENTS.value,
    "resume": DocumentCategory.HR_DOCUMENTS.value,
    "cv": DocumentCategory.HR_DOCUMENTS.value,
    "employee": DocumentCategory.HR_DOCUMENTS.value,
    "onboarding": DocumentCategory.HR_DOCUMENTS.value,
    "timesheet": DocumentCategory.HR_DOCUMENTS.value,
    "payroll": DocumentCategory.HR_DOCUMENTS.value,
    "offer_letter": DocumentCategory.HR_DOCUMENTS.value,

    # 3. Financial
    "financial": DocumentCategory.FINANCIAL.value,
    "finance": DocumentCategory.FINANCIAL.value,
    "financial_report": DocumentCategory.FINANCIAL.value,
    "invoice": DocumentCategory.FINANCIAL.value,
    "receipt": DocumentCategory.FINANCIAL.value,
    "bill": DocumentCategory.FINANCIAL.value,
    "billing_statement": DocumentCategory.FINANCIAL.value,
    "purchase_order": DocumentCategory.FINANCIAL.value,
    "expense_claim": DocumentCategory.FINANCIAL.value,
    "tax_return": DocumentCategory.FINANCIAL.value,
    "balance_sheet": DocumentCategory.FINANCIAL.value,
    "audit_report": DocumentCategory.FINANCIAL.value,
    "bank_statement": DocumentCategory.FINANCIAL.value,

    # 4. General with confidentiality
    "general_confidential": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "general with confidentiality": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "general_with_confidentiality": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "general": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "contract": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "agreement": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "nda": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "lease": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "identity_document": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "passport": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "driver_license": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "id_card": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "kyc": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "policy_document": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "policy": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "handbook": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "sop": DocumentCategory.GENERAL_CONFIDENTIAL.value,
    "other": DocumentCategory.GENERAL_CONFIDENTIAL.value,
}


class ClassificationResult(BaseModel):
    """Encapsulated result of document classification, hiding internal LLM details."""
    category: DocumentCategory = Field(description="The predicted canonical category of the document.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score clamped between 0.0 and 1.0.")


class ClassificationError(Exception):
    """Raised when document classification fails for any reason."""


def classify_document(text: str) -> ClassificationResult:
    """
    Classify the document text into one of the 4 domains using OpenRouter Jev model.
    1) academics
    2) hr_documents
    3) financial
    4) general_confidential
    """
    if not text or not text.strip():
        raise ClassificationError("Document text is empty or missing.")

    # Support primary OPENROUTER_API_KEY with fallbacks for legacy/local test keys
    api_key = (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("JEV_API_KEY")
        or os.environ.get("TYPESAFE_API_KEY")
    )
    if not api_key:
        raise ClassificationError("OPENROUTER_API_KEY environment variable is not set.")

    try:
        response = httpx.post(
            "https://openrouter.ai/api/alpha/decisions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-OpenRouter-Title": "Kagaz",
            },
            json={
                "model": "~typesafe/jev-latest",
                "state": {"document_text": text[:10000]},
                "questions": {
                    "category": {
                        "type": "choice",
                        "instructions": (
                            "Based on the document_text, which single category best describes the main purpose and domain "
                            "of this document? Choose between academics, hr_documents, financial, and general_confidential."
                        ),
                        "criteria": {
                            DocumentCategory.ACADEMICS.value: (
                                "Academic records, transcripts, diplomas, degrees, educational certificates, "
                                "student enrollment records, marksheets, syllabi, coursework, assignments, "
                                "lecture notes, exam papers, research papers, theses, report cards"
                            ),
                            DocumentCategory.HR_DOCUMENTS.value: (
                                "Human resources documents, resumes, CVs, employee onboarding forms, offer letters, "
                                "payroll stubs, performance reviews, benefits enrollment, timesheets, timecards, HR checklists"
                            ),
                            DocumentCategory.FINANCIAL.value: (
                                "Financial documents, invoices, receipts, bills, purchase orders, expense claims, "
                                "utility bills, billing statements, tax returns, W-2s, 1099s, balance sheets, "
                                "income statements, audit reports, bank statements"
                            ),
                            DocumentCategory.GENERAL_CONFIDENTIAL.value: (
                                "General documents with confidentiality requirements, contracts, NDAs, lease agreements, "
                                "vendor agreements, memorandums of understanding (MOU), settlement agreements, "
                                "terms of service, employee handbooks, company policies, standard operating procedures (SOP), "
                                "passports, driver's licenses, national ID cards, visas, KYC compliance documents, "
                                "and sensitive correspondence"
                            ),
                        },
                    }
                },
            },
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()

        # Parse response safely supporting both OpenRouter alpha decisions shape and mock/flat fallbacks
        decision_val, raw_conf, probabilities = _extract_decision_fields(data)

        if not decision_val or not str(decision_val).strip():
            raise ValueError(f"No decision choice found in response: {str(data)[:300]}")

        # Resolve category with case-insensitivity and alias normalization
        normalized_str = str(decision_val).strip().lower().replace("-", "_")
        resolved_category = CATEGORY_ALIASES.get(normalized_str)

        if not resolved_category:
            valid_categories = {c.value for c in DocumentCategory}
            if normalized_str in valid_categories:
                resolved_category = normalized_str
            else:
                resolved_category = DocumentCategory.GENERAL_CONFIDENTIAL.value

        # Handle confidence resolution and bounds clamping
        confidence_score = _calculate_confidence(resolved_category, decision_val, raw_conf, probabilities)

        return ClassificationResult(
            category=DocumentCategory(resolved_category),
            confidence=round(confidence_score, 4),
        )

    except Exception as error:
        raise ClassificationError(f"OpenRouter Jev Classification failed: {error}") from error


def _extract_decision_fields(data: Any) -> tuple[Optional[str], Optional[float], Dict[str, Any]]:
    """Extract decision choice, raw confidence, and probabilities from response payload."""
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict response, got {type(data).__name__}")

    # Standard OpenRouter Alpha Decisions response shape
    answers = data.get("answers")
    if isinstance(answers, dict) and "category" in answers:
        cat_data = answers.get("category", {})
        if isinstance(cat_data, dict):
            choice = cat_data.get("choice") or cat_data.get("decision")
            raw_conf = cat_data.get("confidence")
            probs = cat_data.get("probabilities", {})
            return choice, raw_conf, probs if isinstance(probs, dict) else {}

    # Flat or direct fallback response shape (e.g. mock servers or testing responses)
    choice = data.get("category") or data.get("decision") or data.get("choice")
    raw_conf = data.get("confidence")
    probs = data.get("probabilities", {})
    return choice, raw_conf, probs if isinstance(probs, dict) else {}


def _calculate_confidence(
    resolved_category: str,
    raw_decision: Any,
    raw_conf: Optional[float],
    probabilities: Dict[str, Any],
) -> float:
    """Calculate and safely clamp confidence score between 0.0 and 1.0."""
    conf = 1.0

    if probabilities:
        # Check if probability exists for resolved or raw choice
        if str(raw_decision) in probabilities:
            conf = probabilities[str(raw_decision)]
        elif resolved_category in probabilities:
            conf = probabilities[resolved_category]
        elif raw_conf is not None:
            conf = raw_conf
    elif raw_conf is not None:
        conf = raw_conf

    try:
        conf_float = float(conf)
    except (ValueError, TypeError):
        conf_float = 1.0

    # Clamp strictly between 0.0 and 1.0
    return max(0.0, min(1.0, conf_float))
