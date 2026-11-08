"""
Pydantic schemas for BE-09 Document Validation.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ValidationIssue(BaseModel):
    rule: str = Field(..., description="The policy rule evaluated")
    severity: str = Field("ERROR", description="ERROR or WARNING")
    message: str = Field(..., description="Explanation of violation or discrepancy")


class ValidationEvidence(BaseModel):
    source: str = Field(..., description="Source policy document name or title")
    reference: str = Field(..., description="Section, paragraph, or clause citation")


class ValidationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    status: str = Field(..., description="PASS, FAIL, or REVIEW_REQUIRED")
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    issues: List[ValidationIssue] = []
    evidence: List[ValidationEvidence] = []
    validated_at: Optional[datetime] = None
