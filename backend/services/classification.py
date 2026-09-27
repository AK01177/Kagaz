import enum
import os
from pydantic import BaseModel, Field
from typesafe_sdk import Choice, TypeSafeClient

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
    Classify the document text into one of the known categories using the Jev decision model
    hosted on OpenRouter.
    """
    if not text or not text.strip():
        raise ClassificationError("Document text is empty or missing.")

    # We use OpenRouter API key to access the TypeSafe model
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ClassificationError("OPENROUTER_API_KEY environment variable is not set.")

    try:
        # Initialize the Jev client pointing to OpenRouter's API base URL
        client = TypeSafeClient(
            api_key=api_key,
            base_url="https://openrouter.ai/api"
        )
        
        # We ask Jev a "Choice" question to pick exactly one category
        questions = {
            "category": Choice(
                instructions="Classify the document into one of the following categories based on its text.",
                criteria={
                    "invoice": None,
                    "contract": None,
                    "hr_form": None,
                    "academic_record": None,
                    "other": None
                }
            )
        }
        
        # Send the first 10,000 characters of the document text to Jev (via OpenRouter)
        # Using the specific OpenRouter Jev model identifier
        result = client.system_one(
            state=text[:10000], 
            questions=questions,
            model="typesafe/jev-1.13"
        )
        
        # Extract the decision from the response
        decision = result.choices["category"]
        
        # Return our structured Pydantic model
        return ClassificationResult(
            category=DocumentCategory(decision.choice),
            confidence=decision.confidence
        )
        
    except Exception as error:
        # If anything goes wrong (network issue, missing API key, etc.), we catch it here
        raise ClassificationError(f"Classification failed: {error}") from error
