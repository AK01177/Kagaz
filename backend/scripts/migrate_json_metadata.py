"""
backend/scripts/migrate_json_metadata.py

DB-03: Safe, repeatable migration utility for importing existing demo JSON
document metadata and extraction results into PostgreSQL.

Usage:
    python -m scripts.migrate_json_metadata --dry-run
    python -m scripts.migrate_json_metadata --storage-dir storage_data
"""
import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session

from app.crud.extraction import create_extraction, create_extraction_run
from app.models.document import Document, DocumentStatus
from app.models.extraction import ExtractionStatus
from app.schemas.extraction import ExtractionCreate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_json_metadata")


@dataclass
class MigrationResult:
    scanned: int = 0
    migrated: int = 0
    skipped: int = 0
    failed: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)


def parse_iso_datetime(value: Optional[str]) -> datetime:
    """Parse an ISO-8601 string into a timezone-aware UTC datetime."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        clean_val = value.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_val)
    except Exception:
        return datetime.now(timezone.utc)


def migrate_json_records(
    db: Session,
    storage_dir: Path,
    dry_run: bool = False,
    default_org_id: str = "dev_org",
    default_user_id: str = "dev_user",
) -> MigrationResult:
    """Migrate demo JSON metadata records from storage_dir/metadata into PostgreSQL.

    - Preserves original JSON files and binaries.
    - Idempotent: skips records that already exist in the database.
    - Validates structure and handles missing/malformed fields gracefully.
    - Links Document -> ExtractionRun -> Extracted fields if extracted_fields exist.
    """
    result = MigrationResult()
    metadata_dir = storage_dir / "metadata"

    if not metadata_dir.is_dir():
        logger.info("Metadata directory does not exist: %s (no records to migrate)", metadata_dir)
        return result

    json_files = sorted(metadata_dir.glob("*.json"))
    result.scanned = len(json_files)
    logger.info("Found %d JSON metadata file(s) in %s", len(json_files), metadata_dir)

    for json_file in json_files:
        doc_id = json_file.stem
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            result.failed += 1
            reason = f"Malformed JSON: {exc}"
            logger.error("Failed to read %s: %s", json_file.name, reason)
            result.details.append({"file": json_file.name, "status": "FAILED", "reason": reason})
            continue

        if not isinstance(data, dict):
            result.failed += 1
            reason = "Root JSON content is not a dictionary"
            logger.error("Failed %s: %s", json_file.name, reason)
            result.details.append({"file": json_file.name, "status": "FAILED", "reason": reason})
            continue

        target_id = str(data.get("document_id") or doc_id).strip()
        if not target_id:
            result.failed += 1
            reason = "Missing document identifier"
            result.details.append({"file": json_file.name, "status": "FAILED", "reason": reason})
            continue

        # Check if already present in database
        existing = db.query(Document).filter(Document.id == target_id).first()
        if existing is not None:
            result.skipped += 1
            logger.info("Skipping %s: document already exists in PostgreSQL", target_id)
            result.details.append({
                "file": json_file.name,
                "document_id": target_id,
                "status": "SKIPPED",
                "reason": "Already exists in database",
            })
            continue

        # Resolve storage file path
        storage_path = data.get("storage_path")
        if not storage_path:
            matches = list(storage_dir.glob(f"{target_id}.*"))
            if matches:
                storage_path = str(matches[0].resolve())
            else:
                storage_path = str((storage_dir / f"{target_id}.pdf").resolve())

        # Map document status
        raw_status = str(data.get("status") or "UPLOADED").upper()
        status_map = {
            "UPLOADED": DocumentStatus.UPLOADED,
            "PROCESSING": DocumentStatus.PROCESSING,
            "CLASSIFIED": DocumentStatus.CLASSIFIED,
            "EXTRACTED": DocumentStatus.EXTRACTED,
            "FAILED": DocumentStatus.FAILED,
        }
        status = status_map.get(raw_status, DocumentStatus.UPLOADED)

        # Map attributes with safe defaults
        org_id = str(data.get("organization_id") or default_org_id)
        uploaded_by = str(data.get("submitter_id") or data.get("uploaded_by") or default_user_id)
        filename = str(data.get("filename") or f"{target_id}.pdf")
        file_type = str(data.get("file_type") or "application/pdf")
        file_size = int(data.get("file_size") or 0)
        upload_time = parse_iso_datetime(data.get("uploaded_at"))
        category = data.get("category")
        confidence = float(data.get("confidence")) if data.get("confidence") is not None else None

        extracted_fields = data.get("extracted_fields")
        extracted_confidence = data.get("extracted_confidence") or {}

        if dry_run:
            result.migrated += 1
            logger.info("[DRY-RUN] Would migrate %s (%s, status=%s)", target_id, filename, status.value)
            result.details.append({"file": json_file.name, "document_id": target_id, "status": "WOULD_MIGRATE"})
            continue

        # Persist within a single transaction per document
        try:
            doc = Document(
                id=target_id,
                organization_id=org_id,
                uploaded_by=uploaded_by,
                filename=filename,
                file_type=file_type,
                file_size=file_size,
                storage_path=storage_path,
                status=status,
                upload_timestamp=upload_time,
                classification=category,
                classification_confidence=confidence,
            )
            db.add(doc)
            db.flush()

            # Migrate extractions if present
            if extracted_fields and isinstance(extracted_fields, dict):
                run = create_extraction_run(
                    db,
                    document_id=target_id,
                    status=ExtractionStatus.SUCCESS,
                    document_type=category,
                )
                for field_name, val in extracted_fields.items():
                    if val is None:
                        continue
                    conf_val = float(extracted_confidence.get(field_name, 1.0))
                    conf_val = max(0.0, min(1.0, conf_val))
                    val_str = ", ".join(str(v) for v in val) if isinstance(val, list) else str(val).strip()
                    create_extraction(
                        db,
                        document_id=target_id,
                        extraction_data=ExtractionCreate(
                            field_name=field_name,
                            value=val_str,
                            confidence=conf_val,
                        ),
                        extraction_run_id=run.id,
                    )

            db.commit()
            result.migrated += 1
            logger.info("Migrated document %s successfully", target_id)
            result.details.append({"file": json_file.name, "document_id": target_id, "status": "MIGRATED"})
        except Exception as exc:
            db.rollback()
            result.failed += 1
            reason = f"Database insertion failed: {exc}"
            logger.exception("Failed to migrate document %s: %s", target_id, reason)
            result.details.append({"file": json_file.name, "document_id": target_id, "status": "FAILED", "reason": reason})

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate demo JSON metadata records to PostgreSQL.")
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=Path(os.environ.get("DOCUMENT_STORAGE_DIR", "storage_data")),
        help="Path to documents and metadata directory (default: storage_data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect and report planned migrations without modifying the database.",
    )
    parser.add_argument(
        "--default-org",
        default="dev_org",
        help="Fallback organization ID for records that lack one.",
    )
    parser.add_argument(
        "--default-user",
        default="dev_user",
        help="Fallback submitter user ID for records that lack one.",
    )
    args = parser.parse_args()

    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        summary = migrate_json_records(
            db=db,
            storage_dir=args.storage_dir,
            dry_run=args.dry_run,
            default_org_id=args.default_org,
            default_user_id=args.default_user,
        )
        mode = "DRY-RUN" if args.dry_run else "LIVE"
        logger.info(
            "[%s MIGRATION SUMMARY] Scanned: %d | Migrated: %d | Skipped: %d | Failed: %d",
            mode,
            summary.scanned,
            summary.migrated,
            summary.skipped,
            summary.failed,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

