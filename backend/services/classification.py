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
    Classify the document text into one of the known categories using OpenRouter.
    """
    if not text or not text.strip():
        raise ClassificationError("Document text is empty or missing.")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ClassificationError("OPENROUTER_API_KEY environment variable is not set.")

    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    categories_str = ", ".join([c.value for c in DocumentCategory])

    try:
        import json
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Kagaz Document Workflow"
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a highly accurate document classification AI. Classify the following document text into EXACTLY one of these categories: {categories_str}. You MUST respond with a valid JSON object containing exactly two fields: 'category' (string) and 'confidence' (float between 0.0 and 1.0). Do not include markdown code blocks or any other text."
                    },
                    {
                        "role": "user",
                        "content": text[:15000]
                    }
                ],
            },
            timeout=15.0
        )
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"].strip()
        # Clean up any potential markdown formatting the model might return
        if content.startswith("```json"):
            content = content.replace("```json", "", 1)
        if content.endswith("```"):
            content = content[:-3]
            
        parsed = json.loads(content.strip())
        
        decision_val = parsed.get("category")
        confidence_val = parsed.get("confidence", 1.0)
        
        if not decision_val or decision_val not in [c.value for c in DocumentCategory]:
            decision_val = DocumentCategory.OTHER.value
            
        return ClassificationResult(
            category=DocumentCategory(decision_val),
            confidence=float(confidence_val)
        )
        
    except Exception as error:
        raise ClassificationError(f"OpenRouter Classification failed: {error}") from error

