"""Read and write a document's processing metadata (category, extracted fields, validation, ...).

The database column Document.metadata_json is the durable copy. With local file storage the
same data is also kept in <storage dir>/metadata/<id>.json, and that file wins when present,
so local development behaves as before. With S3 storage there is no local disk to rely on,
so the database is the only copy.
"""
import json
import logging
from copy import deepcopy
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _local_path(storage, document_id: str):
    base_dir = getattr(storage, "base_dir", None)  # S3 storage has no local directory
    return None if base_dir is None else base_dir / "metadata" / f"{document_id}.json"


def _document_row(db: Optional[Session], document_id: str):
    if db is None:
        return None
    from app.models.document import Document

    return db.query(Document).filter(Document.id == document_id).first()


def load_metadata(document_id: str, storage, db: Optional[Session] = None) -> Optional[dict]:
    """Return the stored metadata, or None if the document has none. Raises if it is unreadable."""
    path = _local_path(storage, document_id)
    if path is not None and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    row = _document_row(db, document_id)
    if row is not None and row.metadata_json:
        return deepcopy(row.metadata_json)
    return None


def discard_metadata(document_id: str, storage) -> None:
    """Remove the local metadata file (used to clean up a failed upload)."""
    path = _local_path(storage, document_id)
    if path is not None:
        path.unlink(missing_ok=True)


def save_metadata(document_id: str, metadata: dict, storage, db: Optional[Session] = None) -> None:
    """Save metadata to the database (when the document row exists) and to the local file."""
    path = _local_path(storage, document_id)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        staged = path.with_name(path.name + ".tmp")  # write fully, then swap in, so readers never see half a file
        staged.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        staged.replace(path)
    try:
        row = _document_row(db, document_id)
        if row is not None:
            row.metadata_json = deepcopy(metadata)  # a new object, so SQLAlchemy sees the change
            db.commit()
    except Exception:
        if path is None:  # S3 storage: the database is the only copy, so this must not pass silently
            raise
        logger.warning("Could not save metadata for %s to the database", document_id, exc_info=True)
        db.rollback()
