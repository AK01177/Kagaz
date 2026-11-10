"""
CRUD operations for BE-08 Policy Management.
Enforces multi-tenant isolation and policy version increments.
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.policy import Policy, PolicyVersion
from app.schemas.policy import PolicyCreate, PolicyUpdate


def _next_version(current_ver: str) -> str:
    """Increment version string: v1 -> v2, 1.0 -> 2.0, fallback +1."""
    if current_ver.lower().startswith("v") and current_ver[1:].isdigit():
        return f"v{int(current_ver[1:]) + 1}"
    try:
        return f"v{int(current_ver) + 1}"
    except ValueError:
        return f"{current_ver}.1"


def create_policy(db: Session, organization_id: str, data: PolicyCreate, user_id: Optional[str] = None) -> Policy:
    """Create a new policy and its initial v1 version record."""
    policy = Policy(
        organization_id=organization_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        domain=data.domain.strip().lower(),
        content=data.content,
        current_version="v1",
        created_by=user_id,
    )
    db.add(policy)
    db.flush()

    initial_version = PolicyVersion(
        policy_id=policy.id,
        version="v1",
        content=data.content,
        changelog="Initial policy creation",
        created_by=user_id,
    )
    db.add(initial_version)
    db.commit()
    db.refresh(policy)
    return policy


def get_policy(db: Session, policy_id: str, organization_id: Optional[str] = None) -> Optional[Policy]:
    """Fetch policy by ID, optionally restricted to caller's organization."""
    query = db.query(Policy).filter(Policy.id == policy_id)
    if organization_id:
        query = query.filter(Policy.organization_id == organization_id)
    return query.first()


def list_policies(
    db: Session,
    organization_id: str,
    domain: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> List[Policy]:
    """List organization policies with optional domain and active-status filters."""
    query = db.query(Policy).filter(Policy.organization_id == organization_id)
    if domain:
        query = query.filter(Policy.domain == domain.strip().lower())
    if is_active is not None:
        query = query.filter(Policy.is_active == is_active)
    return query.order_by(Policy.created_at.desc()).all()


def update_policy(db: Session, policy: Policy, data: PolicyUpdate, user_id: Optional[str] = None) -> Policy:
    """Update policy attributes and snapshot a new version if content changed."""
    if data.name is not None:
        policy.name = data.name.strip()
    if data.description is not None:
        policy.description = data.description.strip() if data.description else None
    if data.domain is not None:
        policy.domain = data.domain.strip().lower()
    if data.is_active is not None:
        policy.is_active = data.is_active

    if data.content and data.content != policy.content:
        new_version = _next_version(policy.current_version)
        policy.content = data.content
        policy.current_version = new_version
        version_record = PolicyVersion(
            policy_id=policy.id,
            version=new_version,
            content=data.content,
            changelog=data.changelog or f"Updated policy content to {new_version}",
            created_by=user_id,
        )
        db.add(version_record)

    db.commit()
    db.refresh(policy)
    return policy


def deactivate_policy(db: Session, policy: Policy) -> Policy:
    """Soft-deactivate policy without destroying historical reference records."""
    policy.is_active = False
    db.commit()
    db.refresh(policy)
    return policy


def list_policy_versions(db: Session, policy_id: str) -> List[PolicyVersion]:
    """Retrieve full audit version history for a policy."""
    return db.query(PolicyVersion).filter(PolicyVersion.policy_id == policy_id).order_by(PolicyVersion.created_at.desc()).all()
