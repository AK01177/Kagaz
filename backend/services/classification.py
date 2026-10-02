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
                "state": text[:10000],
                "questions": {
                    "category": {
                        "type": "choice",
                        "instructions": "Which category does this document belong to?",
                        "criteria": {
                            DocumentCategory.INVOICE.value: "Invoices, bills, receipts, purchase orders",
                            DocumentCategory.CONTRACT.value: "Legal contracts, NDAs, lease agreements, terms",
                            DocumentCategory.HR_FORM.value: "Resumes, CVs, employee forms, offer letters, payroll",
                            DocumentCategory.ACADEMIC_RECORD.value: "Transcripts, degrees, diplomas, student records",
                            DocumentCategory.OTHER.value: "Any other general document type"
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
        confidence_val = probabilities.get(decision_val, 1.0) if isinstance(probabilities, dict) else 1.0
        
        if not decision_val or decision_val not in [c.value for c in DocumentCategory]:
            decision_val = DocumentCategory.OTHER.value
            
        return ClassificationResult(
            category=DocumentCategory(decision_val),
            confidence=float(confidence_val)
        )
        
    except Exception as error:
        raise ClassificationError(f"OpenRouter Jev Classification failed: {error}") from error


