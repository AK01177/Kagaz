"""Seed the synthetic policy-validation evaluation corpus into a local Kagaz DB."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEFAULT_CASES = ROOT / "docs" / "policy_validation_evaluation_cases.json"
DEFAULT_MAP = BACKEND / "storage_data" / "policy-validation-evaluation-document-map.json"
ORGANIZATION_ID = "policy-validation-evaluation"
SEED_NAMESPACE = uuid.UUID("afc221f7-15ef-4932-990d-1df2faf41c2a")

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _load_local_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND / ".env")
    except ImportError:
        pass


def _stable_id(name: str) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, name))


def evaluation_user_id(organization_id: str) -> str:
    """Return the stable reviewer user ID seeded for this evaluation tenant."""
    return _stable_id(f"user:{organization_id}")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _collect_policy_specs(cases: list[dict[str, Any]]) -> list[tuple[tuple[str, str | None], dict[str, Any]]]:
    policies: dict[tuple[str, str | None], dict[str, Any]] = {}
    for case in cases:
        policy = case["policy"]
        key = (policy["name"], policy.get("document_type"))
        if key in policies and policies[key]["text"] != policy["text"]:
            raise ValueError(f"Conflicting policy text for {key}")
        policies[key] = policy
    return list(policies.items())


def _evaluation_identity(organization_id: str) -> tuple[str, str, str]:
    user_id = evaluation_user_id(organization_id)
    email = f"policy-eval-{user_id[:12]}@kagaz.local"
    org_suffix = uuid.uuid5(SEED_NAMESPACE, f"org-slug:{organization_id}").hex[:12]
    return user_id, email, f"policy-eval-{org_suffix}"


def seed(cases: list[dict[str, Any]], organization_id: str) -> dict[str, str]:
    from app.db.session import SessionLocal
    from app.models.document import Document, DocumentStatus
    from app.models.extraction import Extraction
    from app.models.policy import (
        Policy,
        PolicyChunk,
        PolicyClassification,
        EMBEDDING_DIMENSION,
        PolicyVersion,
        PolicyVersionStatus,
    )
    from app.models.membership import Membership, MembershipRole
    from app.models.organization import Organization
    from app.models.user import User
    from services.policy_retrieval import create_embeddings

    if SessionLocal is None:
        raise RuntimeError("Could not initialize a database session; check DATABASE_URL")

    db = SessionLocal()
    document_map: dict[str, str] = {}
    try:
        # Confirm the database before making a paid embedding request.
        db.execute(text("SELECT 1"))
        db.commit()
        policy_specs = _collect_policy_specs(cases)
        vectors = create_embeddings([policy["text"] for _, policy in policy_specs])
        if len(vectors) != len(policy_specs) or any(len(vector) != EMBEDDING_DIMENSION for vector in vectors):
            raise RuntimeError("Embedding service returned vectors with an unexpected size")

        # Seed stable, namespaced fixture IDs. This is safe to rerun and does not
        # touch non-evaluation organizations or records.
        expected_name = "Policy validation evaluation fixtures"
        user_id, email, org_slug = _evaluation_identity(organization_id)
        organization = db.get(Organization, organization_id)
        if organization is None:
            organization = Organization(
                id=organization_id,
                name=expected_name,
                slug=org_slug,
                is_active=True,
            )
            db.add(organization)
        else:
            if organization.name != expected_name or organization.slug != org_slug:
                raise ValueError(
                    "The selected organization ID already belongs to another organization; "
                    "choose a new POLICY_EVAL_ORGANIZATION_ID."
                )
            organization.is_active = True

        user = db.get(User, user_id)
        if user is None:
            user = User(
                id=user_id,
                email=email,
                full_name="Policy Evaluation Reviewer",
                is_active=True,
            )
            db.add(user)
        else:
            if user.email != email:
                raise ValueError("The stable evaluation user ID belongs to another account; choose a new evaluation organization ID.")
            user.is_active = True

        membership = db.query(Membership).filter(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        ).first()
        if membership is None:
            db.add(Membership(
                id=_stable_id(f"membership:{organization_id}:{user_id}"),
                organization_id=organization_id,
                user_id=user_id,
                role=MembershipRole.REVIEWER,
                is_active=True,
            ))
        else:
            membership.role = MembershipRole.REVIEWER
            membership.is_active = True
        db.flush()

        for index, ((name, doc_type), policy) in enumerate(policy_specs):
            text = policy["text"]
            policy_id = _stable_id(f"policy:{organization_id}:{name}:{doc_type}")
            version_id = _stable_id(f"version:{policy_id}:eval-v1")
            source_id = _stable_id(f"source:{policy_id}")
            source = db.get(Document, source_id)
            if source is None:
                source = Document(
                    id=source_id,
                    organization_id=organization_id,
                    uploaded_by="policy-evaluation-seeder",
                    filename=f"{_slug(name)}.txt",
                    file_type="text/plain",
                    file_size=len(text.encode("utf-8")),
                    storage_path=f"evaluation-fixture://{policy_id}",
                    status=DocumentStatus.CLASSIFIED,
                    classification=doc_type,
                    classification_confidence=1.0,
                )
                db.add(source)
            else:
                source.filename = f"{_slug(name)}.txt"
                source.file_size = len(text.encode("utf-8"))
                source.classification = doc_type

            record = db.get(Policy, policy_id)
            if record is None:
                record = Policy(
                    id=policy_id,
                    organization_id=organization_id,
                    name=name,
                    description="Synthetic policy for the policy-validation evaluation corpus.",
                    classification=PolicyClassification.INTERNAL,
                    domain="financial",
                    document_type=doc_type,
                    current_version="eval-v1",
                    content=text,
                    is_active=True,
                    created_by="policy-evaluation-seeder",
                )
                db.add(record)
            else:
                record.name = name
                record.classification = PolicyClassification.INTERNAL
                record.domain = "financial"
                record.document_type = doc_type
                record.current_version = "eval-v1"
                record.content = text
                record.is_active = True

            db.query(PolicyVersion).filter(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.status == PolicyVersionStatus.ACTIVE,
            ).update(
                {PolicyVersion.status: PolicyVersionStatus.ARCHIVED},
                synchronize_session=False,
            )

            version = db.get(PolicyVersion, version_id)
            if version is None:
                version = PolicyVersion(
                    id=version_id,
                    policy_id=policy_id,
                    source_document_id=source_id,
                    version="eval-v1",
                    status=PolicyVersionStatus.ACTIVE,
                    content=text,
                    changelog="Synthetic evaluation fixture.",
                    created_by="policy-evaluation-seeder",
                )
                db.add(version)
            else:
                version.source_document_id = source_id
                version.version = "eval-v1"
                version.status = PolicyVersionStatus.ACTIVE
                version.content = text

            chunk_id = _stable_id(f"chunk:{version_id}:0")
            chunk = db.get(PolicyChunk, chunk_id)
            if chunk is None:
                chunk = PolicyChunk(
                    id=chunk_id,
                    policy_version_id=version_id,
                    content=text,
                    embedding=vectors[index],
                    page_number=1,
                    section="Evaluation fixture",
                    chunk_index=0,
                    chunk_metadata={"synthetic_evaluation": True},
                )
                db.add(chunk)
            else:
                chunk.content = text
                chunk.embedding = vectors[index]

        db.flush()
        for case in cases:
            case_id = case["case_id"]
            document_id = _stable_id(f"document:{organization_id}:{case_id}")
            document = db.get(Document, document_id)
            if document is None:
                document = Document(
                    id=document_id,
                    organization_id=organization_id,
                    uploaded_by="policy-evaluation-seeder",
                    filename=f"{case_id}.json",
                    file_type="application/json",
                    file_size=0,
                    storage_path=f"evaluation-fixture://{case_id}",
                    status=DocumentStatus.CLASSIFIED,
                )
                db.add(document)
            document.filename = f"{case_id}.json"
            document.classification = case["document"]["document_type"]
            document.classification_confidence = 1.0

            db.query(Extraction).filter(Extraction.document_id == document_id).delete()
            for field_name, value in case["document"]["extractions"].items():
                db.add(Extraction(
                    document_id=document_id,
                    field_name=field_name,
                    value=str(value),
                    confidence=0.99,
                ))
            document_map[case_id] = document_id

        db.commit()
        return document_map
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    _load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--organization-id", default=os.getenv("POLICY_EVAL_ORGANIZATION_ID", ORGANIZATION_ID))
    parser.add_argument("--output", type=Path, default=DEFAULT_MAP)
    args = parser.parse_args()
    try:
        corpus = json.loads(args.cases.read_text(encoding="utf-8"))
        cases = corpus["cases"]
        document_map = seed(cases, args.organization_id)
    except Exception as exc:
        print(
            f"Evaluation seed failed ({type(exc).__name__}). Check database, embedding-service, and seed configuration.",
            file=sys.stderr,
        )
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document_map, indent=2) + "\n", encoding="utf-8")
    print(f"Seeded {len(cases)} documents and wrote the document map to {args.output}")
    print(f"Evaluation organization: {args.organization_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
