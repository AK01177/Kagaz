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
    Classify the document text into one of the known categories using the Jev API.
    """
    if not text or not text.strip():
        raise ClassificationError("Document text is empty or missing.")

    # We use TypeSafe API key to access the TypeSafe model
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise ClassificationError("TYPESAFE_API_KEY environment variable is not set.")

    try:
        response = httpx.post(
            "https://api.jevai.org/v1/decisions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "mode": "classifier",
                "schema_version": "v1",
                "input": {
                    "context": text[:10000],
                    "classes": [c.value for c in DocumentCategory]
                }
            },
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract the decision from the response
        decision_val = data.get("decision") or data.get("category") or data.get("choice")
        confidence_val = data.get("confidence", 1.0)
        
        if not decision_val:
            raise ValueError(f"Unexpected API response shape: {data}")
        
        # Return our structured Pydantic model
        return ClassificationResult(
            category=DocumentCategory(decision_val),
            confidence=confidence_val
        )
        
    except Exception as error:
        # If anything goes wrong (network issue, missing API key, etc.), we catch it here
        raise ClassificationError(f"Classification failed: {error}") from error
