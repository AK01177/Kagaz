"""
AI-06: Structured Extraction Service
Converts classified document text into structured fields conforming to defined schemas.
Independent from the API layer with robust error handling and type validation.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Type

import httpx

from app.schemas.extraction import (
    BaseDocumentExtraction,
    ExtractedField,
    ExtractionDocumentType,
    get_extraction_schema,
    get_field_definitions,
)

logger = logging.getLogger(__name__)

DEFAULT_EXTRACTION_MODEL = os.environ.get(
    "EXTRACTION_MODEL", "meta-llama/llama-3.3-70b-instruct"
)


class StructuredExtractionError(Exception):
    """Raised when structured field extraction fails or input is invalid."""


class UnsupportedDocumentTypeError(StructuredExtractionError):
    """Raised when an extraction schema does not exist for the document type."""


def extract_structured_fields(
    text: str,
    document_type: str | ExtractionDocumentType,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    client: Optional[httpx.Client] = None,
) -> BaseDocumentExtraction:
    """
    Extract structured key-value fields from document text according to the document type schema.

    Args:
        text: Normalized text extracted from the document.
        document_type: Classified type of the document (e.g. "invoice", "resume", "hr_form").
        api_key: Optional OpenRouter API key; falls back to environment variables.
        model: Optional LLM model slug.
        client: Optional httpx.Client for dependency injection and mocking.

    Returns:
        Populated Pydantic schema instance inheriting from BaseDocumentExtraction.
    """
    if not text or not text.strip():
        raise StructuredExtractionError("Document text is empty or missing.")

    schema_cls = get_extraction_schema(document_type)
    if not schema_cls:
        raise UnsupportedDocumentTypeError(
            f"No extraction schema registered for document type: '{document_type}'"
        )

    resolved_api_key = (
        api_key
        or os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("JEV_API_KEY")
        or os.environ.get("TYPESAFE_API_KEY")
    )
    if not resolved_api_key:
        raise StructuredExtractionError("OPENROUTER_API_KEY environment variable is not set.")

    prompt_model = model or DEFAULT_EXTRACTION_MODEL
    prompt = _build_extraction_prompt(text[:12000], document_type, schema_cls)

    try:
        if client is not None:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {resolved_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-OpenRouter-Title": "Kagaz",
                },
                json={
                    "model": prompt_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an expert structured data extraction engine. "
                                "Extract information from document text strictly adhering to the JSON schema. "
                                "Return only valid JSON without explanation or markdown wrap."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                },
                timeout=30.0,
            )
        else:
            with httpx.Client(timeout=30.0) as http_client:
                response = http_client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {resolved_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:3000",
                        "X-OpenRouter-Title": "Kagaz",
                    },
                    json={
                        "model": prompt_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are an expert structured data extraction engine. "
                                    "Extract information from document text strictly adhering to the JSON schema. "
                                    "Return only valid JSON without explanation or markdown wrap."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"},
                    },
                )
        response.raise_for_status()
        data = response.json()

        raw_content = _extract_completion_content(data)
        parsed_json = _parse_model_json(raw_content)

        return parse_and_validate_fields(parsed_json, schema_cls)

    except (StructuredExtractionError, UnsupportedDocumentTypeError):
        raise
    except Exception as exc:
        logger.exception("Structured extraction failed for document type %s", document_type)
        raise StructuredExtractionError(f"Structured extraction failed: {exc}") from exc


def parse_and_validate_fields(
    raw_fields: Dict[str, Any],
    schema_cls: Type[BaseDocumentExtraction],
) -> BaseDocumentExtraction:
    """
    Validate, sanitize, and map raw extracted dictionary into the target Pydantic schema.
    Handles nested ExtractedField dictionaries or flat key-value pairs safely.
    """
    if not isinstance(raw_fields, dict):
        # Gracefully construct schema with all missing fields if payload is invalid
        return schema_cls()

    constructed_fields: Dict[str, ExtractedField[Any]] = {}

    for field_name in schema_cls.model_fields:
        raw_entry = raw_fields.get(field_name)

        if raw_entry is None:
            constructed_fields[field_name] = ExtractedField.missing()
            continue

        # If model returned { "value": ..., "confidence": ..., "raw_value": ... }
        if isinstance(raw_entry, dict) and ("value" in raw_entry or "confidence" in raw_entry):
            val = raw_entry.get("value")
            raw_val = raw_entry.get("raw_value")
            try:
                conf = float(raw_entry.get("confidence", 0.95))
            except (ValueError, TypeError):
                conf = 0.95 if val is not None else 0.0
        else:
            # Model returned flat key-value pair e.g. "invoice_number": "INV-102"
            val = raw_entry
            raw_val = str(raw_entry) if raw_entry is not None else None
            conf = 0.95 if raw_entry is not None else 0.0

        # Sanitize and coerce values based on expected field type
        sanitized_val = _sanitize_field_value(field_name, val)

        if sanitized_val is None or (isinstance(sanitized_val, str) and not sanitized_val.strip()):
            constructed_fields[field_name] = ExtractedField.missing()
        else:
            # Ensure confidence is clamped between 0.0 and 1.0
            clamped_conf = max(0.0, min(1.0, conf))
            constructed_fields[field_name] = ExtractedField(
                value=sanitized_val,
                confidence=round(clamped_conf, 4),
                raw_value=raw_val or str(sanitized_val),
                is_present=True,
            )

    return schema_cls(**constructed_fields)


def _sanitize_field_value(field_name: str, val: Any) -> Any:
    """Sanitize and coerce extracted values into expected types (e.g. currency to float, skills to list)."""
    if val is None:
        return None

    # Handle float fields (like total_amount)
    if "amount" in field_name or "total" in field_name or "price" in field_name:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            # Strip currency symbols and whitespace, handle commas
            cleaned = re.sub(r"[^\d.,\-]", "", val.strip())
            if "," in cleaned and "." in cleaned:
                # E.g. "1,234.56"
                cleaned = cleaned.replace(",", "")
            elif "," in cleaned and "." not in cleaned:
                # E.g. European format "1234,56"
                cleaned = cleaned.replace(",", ".")
            try:
                return float(cleaned)
            except ValueError:
                return None

    # Handle list fields (like skills)
    if "skills" in field_name:
        if isinstance(val, list):
            return [str(item).strip() for item in val if str(item).strip()]
        if isinstance(val, str):
            # Comma or newline separated string
            items = re.split(r"[,;\n•|]+", val)
            return [item.strip() for item in items if item.strip()]

    # Handle string fields
    if isinstance(val, str):
        trimmed = val.strip()
        return trimmed if trimmed else None

    return val


def _build_extraction_prompt(
    text: str,
    document_type: str | ExtractionDocumentType,
    schema_cls: Type[BaseDocumentExtraction],
) -> str:
    """Construct a precise prompt specifying required fields and output format."""
    field_defs = get_field_definitions(document_type)
    fields_desc = []
    for f_name, f_info in field_defs.items():
        fields_desc.append(f"- {f_name}: {f_info.get('description', '')}")

    fields_block = "\n".join(fields_desc)

    return f"""Document Type: {document_type}

Fields to extract:
{fields_block}

Document Text:
\"\"\"
{text}
\"\"\"

Instructions:
Extract the specified fields from the document text.
For each field, return an object containing:
- "value": the extracted value (or null if absent/missing)
- "confidence": confidence between 0.0 and 1.0 (0.0 if not found)
- "raw_value": exact substring from document text as evidence (or null if not found)

Output JSON format example:
{{
  "field_name": {{
    "value": "...",
    "confidence": 0.95,
    "raw_value": "..."
  }}
}}
"""


def _extract_completion_content(data: Any) -> str:
    """Extract raw message content from chat completion response."""
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response structure: {type(data).__name__}")
    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        raise ValueError(f"No choices returned in model response: {data}")
    first_choice = choices[0]
    message = first_choice.get("message", {})
    content = message.get("content", "")
    if not content:
        raise ValueError("Model returned empty content")
    return content


def _parse_model_json(content: str) -> Dict[str, Any]:
    """Parse JSON from content string, stripping any surrounding markdown fences."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        # Strip ```json ... ```
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as err:
        raise ValueError(f"Model output is not valid JSON: {err}. Raw content: {content[:200]}") from err
