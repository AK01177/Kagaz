"""
CRUD operations for Organization model.
"""
import re
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



def unique_slug(db: Session, name: str) -> str:
    """Turn an organization name into a URL-safe slug that no other organization uses."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    slug, n = base, 2
    while get_organization_by_slug(db, slug) is not None:
        slug, n = f"{base}-{n}", n + 1
    return slug
