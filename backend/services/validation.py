"""
BE-09: Document Validation Service.
Evaluates extracted document fields against active organization domain policies.
Generates PASS, FAIL, or REVIEW_REQUIRED verdicts with issue details and policy evidence.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.crud.policy import list_policies
from app.crud.validation import get_validation_result, save_validation_result
from app.models.document import Document
from app.models.policy import Policy
from storage.document_storage import DocumentStorage

logger = logging.getLogger(__name__)

_ACTIVE_WORKFLOW_STATUSES = {
    "SUBMITTED",
    "IN_REVIEW",
    "CHANGES_REQUESTED",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
}


MANDATORY_FIELDS = {
    "financial": ["invoice_number", "total_amount", "supplier_name"],
    "hr_documents": ["candidate_name", "skills"],
    "hr": ["candidate_name", "skills"],
}


def _extract_policy_threshold(policy_content: str) -> Optional[float]:
    """Parse numeric dollar threshold mentioned in policy text (e.g. '$500', '$1,000')."""
    match = re.search(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)", policy_content)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def validate_document(
    document_id: str,
    organization_id: str,
    domain: Optional[str] = None,
    extracted_fields: Optional[Dict[str, Any]] = None,
    extracted_confidence: Optional[Dict[str, float]] = None,
    policy: Optional[Policy] = None,
    db: Optional[Session] = None,
    user_id: Optional[str] = None,
    storage: Optional[DocumentStorage] = None,
) -> Dict[str, Any]:
    """Evaluate document extraction fields against domain policy and record verdict."""
    if not isinstance(organization_id, str) or not organization_id.strip():
        raise ValueError("organization_id is required for document validation.")
    normalized_org = organization_id.strip()

    if policy is not None and policy.organization_id != normalized_org:
        raise PermissionError("Forbidden: Policy belongs to a different organization.")

    if db is not None:
        db_doc = db.query(Document).filter(Document.id == document_id).first()
        if db_doc is not None and db_doc.organization_id != normalized_org:
            raise PermissionError("Forbidden: Document belongs to a different organization.")

    fields = extracted_fields or {}
    confidences = extracted_confidence or {}
    domain_key = (domain or "financial").lower()
    issues: List[Dict[str, str]] = []
    evidence: List[Dict[str, str]] = []

    # 1. Fetch active policy if not provided
    if policy is None and db is not None:
        policies = list_policies(db, organization_id=normalized_org, domain=domain_key, is_active=True)
        if policies:
            policy = policies[0]

    # 2. Check mandatory required fields for document domain
    required = MANDATORY_FIELDS.get(domain_key, [])
    for field in required:
        if not fields.get(field):
            issues.append({
                "rule": f"MANDATORY_{field.upper()}",
                "severity": "ERROR",
                "message": f"Required field '{field}' is missing or empty.",
            })

    # 3. Check extraction confidence threshold
    for field, conf in confidences.items():
        if conf is not None and conf < 0.65:
            issues.append({
                "rule": f"LOW_CONFIDENCE_{field.upper()}",
                "severity": "WARNING",
                "message": f"Extraction confidence for '{field}' is low ({conf:.2f}). Human review recommended.",
            })

    # 4. Check policy-specific limits and thresholds
    policy_id = None
    policy_version = None
    if policy:
        policy_id = policy.id
        policy_version = policy.current_version
        evidence.append({
            "source": policy.name,
            "reference": f"{policy.name} ({policy.current_version})",
        })

        limit = _extract_policy_threshold(policy.content)
        total = fields.get("total_amount")
        if limit is not None and total is not None:
            try:
                numeric_total = float(str(total).replace("$", "").replace(",", ""))
                if numeric_total > limit:
                    issues.append({
                        "rule": "POLICY_LIMIT_EXCEEDED",
                        "severity": "WARNING",
                        "message": f"Total amount (${numeric_total:,.2f}) exceeds policy threshold (${limit:,.2f}).",
                    })
            except (ValueError, TypeError):
                pass
    else:
        evidence.append({
            "source": "Default Baseline Rules",
            "reference": "System Standard Compliance Specification",
        })

    # 5. Determine overall validation status
    if any(issue["severity"] == "ERROR" for issue in issues):
        status = "FAIL"
    elif any(issue["severity"] == "WARNING" for issue in issues):
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"

    result = {
        "document_id": document_id,
        "status": status,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "issues": issues,
        "evidence": evidence,
    }

    # 6. Persist to DB if session provided
    if db is not None:
        try:
            save_validation_result(
                db=db,
                document_id=document_id,
                organization_id=organization_id,
                status=status,
                policy_id=policy_id,
                policy_version=policy_version,
                issues=issues,
                evidence=evidence,
                validated_by=user_id,
            )
            from services.audit import record_audit_event

            record_audit_event(
                db,
                document_id=document_id,
                organization_id=organization_id,
                event_type="DOCUMENT_VALIDATED",
                actor_id=str(user_id) if user_id else "system",
                actor_type="USER" if user_id else "SYSTEM",
                actor_role="REVIEWER" if user_id else "SYSTEM",
                details={
                    "validation_status": status,
                    "policy_id": policy_id,
                    "policy_version": policy_version,
                    "issue_count": len(issues),
                },
                commit=True,
                ensure_document_exists=True,
            )
        except Exception as e:
            logger.warning("Failed to persist validation result to DB for %s: %s", document_id, e)

    # 7. Update JSON sidecar metadata for fast local read
    try:
        storage = storage or DocumentStorage()
        metadata_path = storage.base_dir / "metadata" / f"{document_id}.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["validation"] = result
            # Validation findings stay separate from human workflow/approval state:
            # only set pre-review sidecar status when the document is not already in workflow.
            if meta.get("status") not in _ACTIVE_WORKFLOW_STATUSES:
                if status == "PASS":
                    meta["status"] = "VALIDATED"
                elif status == "REVIEW_REQUIRED":
                    meta["status"] = "REVIEW_REQUIRED"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
    except Exception as e:
        logger.debug("Failed updating JSON metadata with validation for %s: %s", document_id, e)

    return result
