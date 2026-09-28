import os
import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")
api_key = os.environ.get("TYPESAFE_API_KEY")

print("Key starts with:", api_key[:10] if api_key else "None")

try:
    response = httpx.post(
        "https://api.jevai.org/v1/decisions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "mode": "classifier",
            "schema_version": "v1",
            "input": {
                "context": "This is a test invoice document for $500.",
                "classes": ["invoice", "contract", "other"]
            }
        },
        timeout=10
    )
    print("Status:", response.status_code)
    print("Body:", response.text)
except Exception as e:
    print("Error:", e)
