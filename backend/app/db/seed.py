"""
DB-02: Test and Development Seed Data.
Seeds at least two isolated organizations with distinct users, provider mappings, and roles.
"""
import os
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

try:
    from app.models.membership import Membership, MembershipRole
    from app.models.organization import Organization
    from app.models.user import User, UserProviderMapping
    from services.password import hash_password
except ImportError:
    from backend.app.models.membership import Membership, MembershipRole
    from backend.app.models.organization import Organization
    from backend.app.models.user import User, UserProviderMapping
    from backend.services.password import hash_password


def seed_two_organizations(
    db: Session,
    *,
    default_password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Seed at least two isolated organizations into the database.
    
    Organization 1: Acme Corporation ('acme-corp')
      - Alice Smith (alice@acme.com) -> ORG_ADMIN
      - Bob Jones (bob@acme.com) -> SUBMITTER
      - Charlie Clark (charlie@acme.com) -> REVIEWER

    Organization 2: Beta Logistics ('beta-logistics')
      - David Miller (david@beta.com) -> ORG_ADMIN
      - Eve Taylor (eve@beta.com) -> SUBMITTER
      - Frank Wright (frank@beta.com) -> REVIEWER

    Ensures strict tenant isolation: users in Acme belong only to Acme,
    and users in Beta belong only to Beta.
    """
    # 1. Organization A: Acme Corporation
    org_a = db.query(Organization).filter(Organization.slug == "acme-corp").first()
    if not org_a:
        org_a = Organization(
            name="Acme Corporation",
            slug="acme-corp",
            is_active=True,
        )
        db.add(org_a)
        db.flush()

    # Users for Org A
    user_alice = db.query(User).filter(User.email == "alice@acme.com").first()
    if not user_alice:
        user_alice = User(
            email="alice@acme.com",
            full_name="Alice Smith",
            provider="google",
            provider_subject="google_sub_alice_101",
            is_active=True,
        )
        db.add(user_alice)
        db.flush()
        db.add(
            UserProviderMapping(
                user_id=user_alice.id,
                provider="google",
                provider_subject="google_sub_alice_101",
            )
        )

    user_bob = db.query(User).filter(User.email == "bob@acme.com").first()
    if not user_bob:
        user_bob = User(
            email="bob@acme.com",
            full_name="Bob Jones",
            provider="google",
            provider_subject="google_sub_bob_102",
            is_active=True,
        )
        db.add(user_bob)
        db.flush()
        db.add(
            UserProviderMapping(
                user_id=user_bob.id,
                provider="google",
                provider_subject="google_sub_bob_102",
            )
        )

    user_charlie = db.query(User).filter(User.email == "charlie@acme.com").first()
    if not user_charlie:
        user_charlie = User(
            email="charlie@acme.com",
            full_name="Charlie Clark",
            provider="google",
            provider_subject="google_sub_charlie_103",
            is_active=True,
        )
        db.add(user_charlie)
        db.flush()

    # Memberships for Org A
    mem_alice_a = (
        db.query(Membership)
        .filter(Membership.organization_id == org_a.id, Membership.user_id == user_alice.id)
        .first()
    )
    if not mem_alice_a:
        mem_alice_a = Membership(
            organization_id=org_a.id,
            user_id=user_alice.id,
            role=MembershipRole.ORG_ADMIN,
            is_active=True,
        )
        db.add(mem_alice_a)

    mem_bob_a = (
        db.query(Membership)
        .filter(Membership.organization_id == org_a.id, Membership.user_id == user_bob.id)
        .first()
    )
    if not mem_bob_a:
        mem_bob_a = Membership(
            organization_id=org_a.id,
            user_id=user_bob.id,
            role=MembershipRole.SUBMITTER,
            is_active=True,
        )
        db.add(mem_bob_a)

    mem_charlie_a = (
        db.query(Membership)
        .filter(Membership.organization_id == org_a.id, Membership.user_id == user_charlie.id)
        .first()
    )
    if not mem_charlie_a:
        mem_charlie_a = Membership(
            organization_id=org_a.id,
            user_id=user_charlie.id,
            role=MembershipRole.REVIEWER,
            is_active=True,
        )
        db.add(mem_charlie_a)

    # 2. Organization B: Beta Logistics
    org_b = db.query(Organization).filter(Organization.slug == "beta-logistics").first()
    if not org_b:
        org_b = Organization(
            name="Beta Logistics",
            slug="beta-logistics",
            is_active=True,
        )
        db.add(org_b)
        db.flush()

    # Users for Org B
    user_david = db.query(User).filter(User.email == "david@beta.com").first()
    if not user_david:
        user_david = User(
            email="david@beta.com",
            full_name="David Miller",
            provider="azure_ad",
            provider_subject="azure_sub_david_201",
            is_active=True,
        )
        db.add(user_david)
        db.flush()
        db.add(
            UserProviderMapping(
                user_id=user_david.id,
                provider="azure_ad",
                provider_subject="azure_sub_david_201",
            )
        )

    user_eve = db.query(User).filter(User.email == "eve@beta.com").first()
    if not user_eve:
        user_eve = User(
            email="eve@beta.com",
            full_name="Eve Taylor",
            provider="azure_ad",
            provider_subject="azure_sub_eve_202",
            is_active=True,
        )
        db.add(user_eve)
        db.flush()
        db.add(
            UserProviderMapping(
                user_id=user_eve.id,
                provider="azure_ad",
                provider_subject="azure_sub_eve_202",
            )
        )

    user_frank = db.query(User).filter(User.email == "frank@beta.com").first()
    if not user_frank:
        user_frank = User(
            email="frank@beta.com",
            full_name="Frank Wright",
            provider="azure_ad",
            provider_subject="azure_sub_frank_203",
            is_active=True,
        )
        db.add(user_frank)
        db.flush()

    # Memberships for Org B
    mem_david_b = (
        db.query(Membership)
        .filter(Membership.organization_id == org_b.id, Membership.user_id == user_david.id)
        .first()
    )
    if not mem_david_b:
        mem_david_b = Membership(
            organization_id=org_b.id,
            user_id=user_david.id,
            role=MembershipRole.ORG_ADMIN,
            is_active=True,
        )
        db.add(mem_david_b)

    mem_eve_b = (
        db.query(Membership)
        .filter(Membership.organization_id == org_b.id, Membership.user_id == user_eve.id)
        .first()
    )
    if not mem_eve_b:
        mem_eve_b = Membership(
            organization_id=org_b.id,
            user_id=user_eve.id,
            role=MembershipRole.SUBMITTER,
            is_active=True,
        )
        db.add(mem_eve_b)

    mem_frank_b = (
        db.query(Membership)
        .filter(Membership.organization_id == org_b.id, Membership.user_id == user_frank.id)
        .first()
    )
    if not mem_frank_b:
        mem_frank_b = Membership(
            organization_id=org_b.id,
            user_id=user_frank.id,
            role=MembershipRole.REVIEWER,
            is_active=True,
        )
        db.add(mem_frank_b)

    if default_password:
        for seeded_user in (user_alice, user_bob, user_charlie, user_david, user_eve, user_frank):
            if not seeded_user.password_hash:
                seeded_user.password_hash = hash_password(default_password)

    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "users_a": [user_alice, user_bob, user_charlie],
        "users_b": [user_david, user_eve, user_frank],
        "memberships_a": [mem_alice_a, mem_bob_a, mem_charlie_a],
        "memberships_b": [mem_david_b, mem_eve_b, mem_frank_b],
    }


if __name__ == "__main__":
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        result = seed_two_organizations(
            db,
            default_password=os.environ.get("SEED_DEFAULT_PASSWORD"),
        )
        print(f"Seeded {result['org_a'].name} and {result['org_b'].name} successfully.")
    finally:
        db.close()

