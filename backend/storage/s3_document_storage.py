import os

from storage.document_storage import DocumentStorage
from storage.s3_policy_storage import S3PolicyStorage

DOCUMENT_PREFIX = "documents/"


class S3DocumentStorage(S3PolicyStorage):
    """S3-backed storage for user-uploaded documents (objects live under documents/)."""

    prefix = DOCUMENT_PREFIX

    def open_stream(self, document_id: str):
        """Return (extension, streaming body) so large files are not buffered in memory."""
        key = self._find_key(document_id)
        if key is None:
            return None
        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        return os.path.splitext(key)[1], body


def get_document_storage() -> "S3DocumentStorage | DocumentStorage":
    """S3 when S3_DOCUMENT_BUCKET is set; otherwise the local DOCUMENT_STORAGE_DIR folder."""
    bucket = os.environ.get("S3_DOCUMENT_BUCKET", "").strip()
    return S3DocumentStorage(bucket) if bucket else DocumentStorage()
