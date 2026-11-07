"""
CRUD operations for Membership model.
"""
from typing import List, Optional
from sqlalchemy.orm import Session

try:
    from app.models.membership import Membership, MembershipRole
    from app.schemas.membership import MembershipCreate, MembershipUpdate
except ImportError:
    from backend.app.models.membership import Membership, MembershipRole
    from backend.app.schemas.membership import MembershipCreate, MembershipUpdate


def create_membership(db: Session, data: MembershipCreate) -> Membership:
    """Create and persist a new Organization Membership."""
    membership = Membership(**data.model_dump(exclude_unset=True))
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def get_membership(db: Session, organization_id: str, user_id: str) -> Optional[Membership]:
    """Retrieve membership record for a specific user in an organization."""
    return (
        db.query(Membership)
        .filter(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
        .first()
    )


def get_user_memberships(db: Session, user_id: str) -> List[Membership]:
    """List all active organization memberships for a user."""
    return (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.is_active.is_(True))
        .all()
    )


def get_organization_memberships(db: Session, organization_id: str) -> List[Membership]:
    """List all memberships within a specific organization."""
    return (
        db.query(Membership)
        .filter(Membership.organization_id == organization_id)
        .all()
    )


# Convenience aliases
list_organization_members = get_organization_memberships
get_user_membership_in_org = get_membership

