"""End-to-end retrieval check with the real stack (Gemini embeddings + pgvector).

Run from `backend/`:
    python -m tests.rag_eval.e2e_check [relevance_floor]   (default: the production floor)

Everything happens in a throwaway schema inside one transaction that is rolled back, so
your real tables are never touched. Uses GEMINI_API_KEY and DATABASE_URL from backend/.env
and a few dozen embedding calls of your free quota.

For each query in queries.json it runs the production path: embed the question, search with
organization/role filters, and apply the relevance floor. It reports whether the clause that
holds the answer was returned, whether unrelated questions were correctly answered with
nothing, and that no organization ever saw another organization's policy.
"""
from __future__ import annotations

import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

HERE = Path(__file__).parent
load_dotenv(HERE.parent.parent / ".env")

from app.db.base import Base  # noqa: E402  (after load_dotenv so settings are read from .env)
from app.models.policy import Policy, PolicyVersion, PolicyVersionStatus  # noqa: E402
from services import policy_retrieval  # noqa: E402
from services.document_types import require_document_type  # noqa: E402
from services.policy_ingestion import index_text_policy_version  # noqa: E402

ORG_IDS = {"A": "org-a", "B": "org-b"}
# The type each evaluation policy is written for, in deliberately different spellings.
POLICY_TYPES = {
    "finance_expense_orgA": "Invoice",
    "finance_limits_orgA": "Invoice",
    "academic_scholarship_orgA": "Transcript",
    "hr_leave_orgA": "HR Forms",
    "hr_leave_orgB": "hr-documents",
}


def _norm(value: str) -> str:
    return " ".join(value.split()).casefold()


def load_policies(db: Session) -> None:
    for path in sorted((HERE / "policies").glob("*.md")):
        org = ORG_IDS[re.search(r"_org([A-Z])", path.stem).group(1)]
        policy = Policy(
            organization_id=org, name=path.stem, domain="eval",
            document_type=require_document_type(POLICY_TYPES[path.stem]),
        )
        db.add(policy)
        db.flush()
        version = PolicyVersion(
            policy_id=policy.id, version="v1", content=path.read_text(encoding="utf-8"),
            status=PolicyVersionStatus.PROCESSING,
        )
        db.add(version)
        db.flush()
        chunks = index_text_policy_version(db, policy, version)
        print(f"  indexed {path.name}: {chunks} chunks ({version.status.value})")
        if not chunks:
            raise SystemExit(f"Indexing failed: {version.ingestion_error}")


@contextmanager
def eval_database(floor: float):
    """A session on a throwaway schema with the evaluation policies indexed; rolled back on exit."""
    policy_retrieval.RELEVANCE_THRESHOLD = floor
    schema = f"e2e_{uuid4().hex}"
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn, conn.begin() as transaction:
        try:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            Base.metadata.create_all(conn, checkfirst=False)
            resolved = conn.scalar(text("SELECT relnamespace::regnamespace::text FROM pg_class WHERE oid = to_regclass('policies')"))
            assert resolved.strip('"') == schema, "tables must live in the throwaway schema"
            with Session(conn) as db:
                print(f"Ingesting policies (relevance floor {floor}) ...")
                load_policies(db)
                yield db
        finally:
            transaction.rollback()  # nothing is kept
    print("\nRolled back: no data was written to your database.")


def run(floor: float) -> None:
    queries = json.loads((HERE / "queries.json").read_text())["queries"]
    with eval_database(floor) as db:
        report(db, queries)


def report(db: Session, queries: list[dict]) -> None:
    tally = {"relevant": [0, 0], "exact": [0, 0], "off_topic": [0, 0], "wrong_type": [0, 0], "near_miss": [0, 0]}  # [good, total]
    wrong_org = 0
    problems = []
    for query in queries:
        org = ORG_IDS.get(query.get("org", "A"))
        embedding = policy_retrieval.create_query_embedding(query["q"])
        result = policy_retrieval.retrieve_policy_evidence(
            db, org, "ORG_ADMIN", embedding, None, query.get("doc_type"), None, 5, query_text=query["q"]
        )
        wrong_org += sum(1 for policy, *_ in result.rows if policy.organization_id != org)
        kind = query["kind"]
        if kind == "relevant":
            bucket = tally["exact" if query.get("exact") else "relevant"]
            good = any(_norm(query["expect"]) in _norm(chunk.content) for _p, _v, chunk, *_ in result.rows)
        elif kind == "wrong_type":
            bucket, good = tally["wrong_type"], not result.rows
        else:
            bucket, good = tally[kind], not result.rows
        bucket[0] += good
        bucket[1] += 1
        if not good:
            detail = f"{len(result.rows)} chunk(s)" if kind != "relevant" else result.outcome
            problems.append(f"[{kind}{'/exact' if query.get('exact') else ''}] {query['q'][:60]!r} -> {detail}")
    labels = {
        "relevant": "Answer clause returned (natural questions)",
        "exact": "Answer clause returned (exact terms: numbers, clause numbers)",
        "off_topic": "Off-topic questions answered with nothing",
        "wrong_type": "Questions from a document of the wrong type answered with nothing",
        "near_miss": "On-topic questions the policies do not cover answered with nothing (informational)",
    }
    print()
    for key, label in labels.items():
        print(f"{label}: {tally[key][0]}/{tally[key][1]}")
    print(f"Results from the wrong organization: {wrong_org} (must be 0)")
    for line in problems:
        print("  -", line)


if __name__ == "__main__":
    run(float(sys.argv[1]) if len(sys.argv) > 1 else policy_retrieval.RELEVANCE_THRESHOLD)
