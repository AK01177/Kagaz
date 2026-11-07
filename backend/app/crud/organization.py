"""
CRUD operations for Organization model.
"""
from typing import Optional
from sqlalchemy.orm import Session

try:
    from app.models.organization import Organization
    from app.schemas.organization import OrganizationCreate, OrganizationUpdate
except ImportError:
    from backend.app.models.organization import Organization
    from backend.app.schemas.organization import OrganizationCreate, OrganizationUpdate


def create_organization(db: Session, data: OrganizationCreate) -> Organization:
    """Create and persist a new Organization."""
    org_dict = data.model_dump(exclude_unset=True)
    org = Organization(**org_dict)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def get_organization(db: Session, organization_id: str) -> Optional[Organization]:
    """Retrieve an Organization by ID."""
    return db.query(Organization).filter(Organization.id == organization_id).first()


def get_organization_by_slug(db: Session, slug: str) -> Optional[Organization]:
    """Retrieve an Organization by its unique slug."""
    return db.query(Organization).filter(Organization.slug == slug.strip().lower()).first()

