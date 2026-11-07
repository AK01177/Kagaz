"""
BE-08: Policy Management API endpoints.
Provides tenant-isolated CRUD operations and version tracking for organization policies.
"""
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import require_reviewer, require_submitter
from app.db.session import get_db
from app.crud.policy import (
    create_policy,
    deactivate_policy,
    get_policy,
    list_policies,
    list_policy_versions,
    update_policy,
)
from app.schemas.policy import (
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
    PolicyVersionResponse,
)

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy_endpoint(
    payload: PolicyCreate,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new policy and initial v1 version for the caller's organization."""
    return create_policy(db, organization_id=user["organization_id"], data=payload, user_id=user.get("sub"))


@router.get("", response_model=List[PolicyResponse])
async def list_policies_endpoint(
    user: Annotated[dict, Depends(require_submitter)],
    db: Annotated[Session, Depends(get_db)],
    domain: Optional[str] = Query(None, description="Filter by policy domain"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive policies"),
):
    """List policies belonging to the authenticated user's organization."""
    return list_policies(db, organization_id=user["organization_id"], domain=domain, is_active=is_active)


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy_endpoint(
    policy_id: str,
    user: Annotated[dict, Depends(require_submitter)],
    db: Annotated[Session, Depends(get_db)],
):
    """Fetch policy details by ID within the caller's organization."""
    policy = get_policy(db, policy_id=policy_id, organization_id=user["organization_id"])
    if not policy:
        raise HTTPException(status_code=404, detail={"code": "POLICY_NOT_FOUND", "message": f"Policy '{policy_id}' not found."})
    return policy


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy_endpoint(
    policy_id: str,
    payload: PolicyUpdate,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update policy attributes and snapshot a new version if content is modified."""
    policy = get_policy(db, policy_id=policy_id, organization_id=user["organization_id"])
    if not policy:
        raise HTTPException(status_code=404, detail={"code": "POLICY_NOT_FOUND", "message": f"Policy '{policy_id}' not found."})
    return update_policy(db, policy=policy, data=payload, user_id=user.get("sub"))


@router.delete("/{policy_id}", response_model=PolicyResponse)
async def delete_policy_endpoint(
    policy_id: str,
    user: Annotated[dict, Depends(require_reviewer)],
    db: Annotated[Session, Depends(get_db)],
):
    """Soft-deactivate a policy within the caller's organization."""
    policy = get_policy(db, policy_id=policy_id, organization_id=user["organization_id"])
    if not policy:
        raise HTTPException(status_code=404, detail={"code": "POLICY_NOT_FOUND", "message": f"Policy '{policy_id}' not found."})
    return deactivate_policy(db, policy=policy)


@router.get("/{policy_id}/versions", response_model=List[PolicyVersionResponse])
async def get_policy_versions_endpoint(
    policy_id: str,
    user: Annotated[dict, Depends(require_submitter)],
    db: Annotated[Session, Depends(get_db)],
):
    """List full audit version history for a policy."""
    policy = get_policy(db, policy_id=policy_id, organization_id=user["organization_id"])
    if not policy:
        raise HTTPException(status_code=404, detail={"code": "POLICY_NOT_FOUND", "message": f"Policy '{policy_id}' not found."})
    return list_policy_versions(db, policy_id=policy_id)
