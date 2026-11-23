"""Demo accounts for manual testing: one login per role, in an isolated demo organization.

Run from the backend folder:  python -m app.db.seed_demo

It creates (safe to re-run):
  1. Supabase logins (auto-confirmed projects only) for each dummy email below.
  2. A "Kagaz Demo" organization with one user per role, plus a second org with one user
     so tenant isolation can be tested. Existing Acme/Beta data is not touched.
"""
import os

import httpx
from dotenv import load_dotenv

from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User

PASSWORD = "KagazDemo#2026"  # dummy accounts only

# (email, full name, role, org slug)
DEMO_USERS = [
    ("demo.sysadmin@kagaz-demo.test", "Demo System Admin", MembershipRole.SYSTEM_ADMIN, "kagaz-demo"),
    ("demo.orgadmin@kagaz-demo.test", "Demo Org Admin", MembershipRole.ORG_ADMIN, "kagaz-demo"),
    ("demo.reviewer@kagaz-demo.test", "Demo Reviewer", MembershipRole.REVIEWER, "kagaz-demo"),
    ("demo.approver@kagaz-demo.test", "Demo Approver", MembershipRole.APPROVER, "kagaz-demo"),
    ("demo.submitter@kagaz-demo.test", "Demo Submitter", MembershipRole.SUBMITTER, "kagaz-demo"),
    ("demo.submitter2@kagaz-demo.test", "Demo Submitter Two", MembershipRole.SUBMITTER, "kagaz-demo"),
    # one person in two organizations with different roles: tests the organization picker
    ("demo.multi@kagaz-demo.test", "Demo Multi-Org User", MembershipRole.SUBMITTER, "kagaz-demo"),
    ("demo.multi@kagaz-demo.test", "Demo Multi-Org User", MembershipRole.REVIEWER, "kagaz-demo-two"),
    ("demo.other@kagaz-demo.test", "Other Org Submitter", MembershipRole.SUBMITTER, "kagaz-demo-two"),
]
ORG_NAMES = {"kagaz-demo": "Kagaz Demo", "kagaz-demo-two": "Kagaz Demo Two"}


def create_supabase_logins() -> None:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    headers = {"apikey": os.environ["SUPABASE_ANON_KEY"], "Content-Type": "application/json"}
    for email, name, _role, _org in DEMO_USERS:
        body = {"email": email, "password": PASSWORD, "data": {"full_name": name}}
        response = httpx.post(f"{url}/auth/v1/signup", headers=headers, json=body, timeout=15)
        print(f"supabase {email}: HTTP {response.status_code}")


def seed_database() -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        orgs = {}
        for slug, name in ORG_NAMES.items():
            org = db.query(Organization).filter(Organization.slug == slug).first()
            if org is None:
                org = Organization(name=name, slug=slug, is_active=True)
                db.add(org)
                db.flush()
            orgs[slug] = org

        for email, name, role, slug in DEMO_USERS:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                # provider is linked automatically on the user's first sign-in
                user = User(email=email, full_name=name, is_active=True)
                db.add(user)
                db.flush()
            member = db.query(Membership).filter(
                Membership.user_id == user.id, Membership.organization_id == orgs[slug].id
            ).first()
            if member is None:
                db.add(Membership(user_id=user.id, organization_id=orgs[slug].id, role=role, is_active=True))
            print(f"db {email}: {role.value} in {slug}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    load_dotenv()
    create_supabase_logins()
    seed_database()
    print(f"\nDone. Password for every demo account: {PASSWORD}")
