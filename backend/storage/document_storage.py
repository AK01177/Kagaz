import os
from pathlib import Path


class DocumentNotFoundError(Exception):
    """Raised when a document cannot be located in storage."""

    def __init__(self, document_id: str):
        self.document_id = document_id
        super().__init__(f"Document '{document_id}' was not found in storage.")


class DocumentStorage:
    """Local filesystem-backed document storage.

    Stands in for the S3-backed storage described in the architecture docs
    until that integration lands. Callers only depend on this interface
    (exists/resolve), so extraction code stays unaware of where documents
    actually live.
    """

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or os.environ.get("DOCUMENT_STORAGE_DIR", "storage_data"))

    def exists(self, document_id: str) -> bool:
        return self._find(document_id) is not None

    def resolve(self, document_id: str) -> Path:
        """Return the path of a stored document, raising if it is missing."""
        path = self._find(document_id)
        if path is None:
            raise DocumentNotFoundError(document_id)
        return path

    def _find(self, document_id: str) -> Path | None:
        if not self.base_dir.is_dir():
            return None
        matches = sorted(self.base_dir.glob(f"{document_id}.*"))
        return matches[0] if matches else None
