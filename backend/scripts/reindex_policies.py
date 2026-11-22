"""Re-embed policies after the embedding model changed (or after a migration from an older setup).

Run from the backend/ folder:
    python -m scripts.reindex_policies

Only ACTIVE versions embedded with a different model (or none) are touched. Needs
GEMINI_API_KEY and DATABASE_URL in backend/.env.
"""
from app.db.session import SessionLocal
from services.policy_ingestion import reindex_stale_versions
from storage.s3_policy_storage import get_policy_storage


def main() -> None:
    if SessionLocal is None:
        raise SystemExit("DATABASE_URL is not configured.")
    storage = get_policy_storage()
    with SessionLocal() as db:
        results = reindex_stale_versions(db, storage)
    if not results:
        print("Nothing to re-index: every active policy version uses the current embedding model.")
    for version_id, chunk_count in results.items():
        print(f"{version_id}: {'re-indexed ' + str(chunk_count) + ' chunks' if chunk_count else 'FAILED (see ingestion_error)'}")


if __name__ == "__main__":
    main()
