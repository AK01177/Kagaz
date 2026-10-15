import enum
import os
import httpx
from pydantic import BaseModel, Field

# Define the valid document categories
class DocumentCategory(str, enum.Enum):
    INVOICE = "invoice"
    CONTRACT = "contract"
    HR_FORM = "hr_form"
    ACADEMIC_RECORD = "academic_record"
    FINANCIAL_REPORT = "financial_report"
    IDENTITY_DOCUMENT = "identity_document"
    POLICY_DOCUMENT = "policy_document"
    OTHER = "other"

# Define what our function returns
class ClassificationResult(BaseModel):
    category: DocumentCategory = Field(description="The predicted category of the document.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0.")

class ClassificationError(Exception):
    """Raised when document classification fails for any reason."""

def classify_document(text: str) -> ClassificationResult:
    """
    Classify the document text into one of the known categories using OpenRouter Jev model.
    """
    if not text or not text.strip():
        raise ClassificationError("Document text is empty or missing.")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ClassificationError("OPENROUTER_API_KEY environment variable is not set.")

    try:
        response = httpx.post(
            "https://openrouter.ai/api/alpha/decisions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-OpenRouter-Title": "Kagaz"
            },
            json={
                "model": "~typesafe/jev-latest",
                # Jev expects "state" to be a key-value object, not a bare string.
                "state": {"document_text": text[:10000]},
                "questions": {
                    "category": {
                        "type": "choice",
                        "instructions": "Based on the document_text, which single category best describes the main purpose of this document? Choose 'other' only if no specific category fits.",
                        "criteria": {
                            DocumentCategory.INVOICE.value: "Invoices, bills, receipts, purchase orders, expense claims, utility bills, billing statements",
                            DocumentCategory.CONTRACT.value: "Contracts, NDAs, lease agreements, terms of service, vendor agreements, memorandums of understanding (MOU), settlement agreements",
                            DocumentCategory.HR_FORM.value: "Resumes, CVs, employee onboarding forms, offer letters, payroll stubs, performance reviews, benefits enrollment, timecards",
                            DocumentCategory.ACADEMIC_RECORD.value: "Transcripts, diplomas, degrees, certificates, student enrollment records, marksheets, syllabi, assignments, lecture notes, exam papers, research papers, theses, letters of recommendation, report cards",
                            DocumentCategory.FINANCIAL_REPORT.value: "Tax returns, W-2s, balance sheets, income statements, audit reports, bank statements, corporate financial disclosures",
                            DocumentCategory.IDENTITY_DOCUMENT.value: "Passports, driver's licenses, national ID cards, visas, KYC compliance documents, voter IDs",
                            DocumentCategory.POLICY_DOCUMENT.value: "Company policies, employee handbooks, compliance guidelines, standard operating procedures (SOP), safety manuals",
                            DocumentCategory.OTHER.value: "Only for documents unrelated to every other category, such as recipes, meeting notes, or casual correspondence"
                        }
                    }
                }
            },
            timeout=15.0
        )
        response.raise_for_status()
        data = response.json()
        
        answers = data.get("answers", {})
        category_answer = answers.get("category", {})
        
        decision_val = category_answer.get("choice")
        probabilities = category_answer.get("probabilities", {})
        confidence_val = probabilities.get(decision_val, category_answer.get("confidence", 1.0)) if isinstance(probabilities, dict) else category_answer.get("confidence", 1.0)

        if not decision_val:
            # Unexpected response shape: fail loudly instead of mislabeling as "other".
            raise ValueError(f"Unexpected response from decisions API: {str(data)[:300]}")
        if decision_val not in [c.value for c in DocumentCategory]:
            decision_val = DocumentCategory.OTHER.value
            
        return ClassificationResult(
            category=DocumentCategory(decision_val),
            confidence=float(confidence_val)
        )
        
    except Exception as error:
        raise ClassificationError(f"OpenRouter Jev Classification failed: {error}") from error


