import os
from pathlib import Path
from tempfile import TemporaryDirectory

from storage.document_storage import DocumentNotFoundError, DocumentStorage

POLICY_PREFIX = "policy_sources/"


class S3PolicyStorage:
    """S3-backed storage for policy source files.

    Mirrors the DocumentStorage interface used by policy ingestion (exists/resolve).
    resolve() downloads the object to a private temp directory and returns the local
    path, so extraction code keeps working on a normal file. Objects live under
    policy_sources/<document_id><extension>; tenant isolation is enforced by the
    database lookups that hand out document ids, exactly as with local storage.
    """

    def __init__(self, bucket: str, region: str | None = None, client=None):
        self.bucket = bucket
        if client is None:
            import boto3  # imported lazily so local-only setups do not need AWS config

            client = boto3.client("s3", region_name=region or os.environ.get("AWS_REGION"))
        self.client = client
        self._cache = TemporaryDirectory(prefix="policy_s3_")

    def key_for(self, document_id: str, extension: str) -> str:
        return f"{POLICY_PREFIX}{document_id}{extension}"

    def storage_path_for(self, document_id: str, extension: str) -> str:
        return f"s3://{self.bucket}/{self.key_for(document_id, extension)}"

    def store(self, local_path: Path, document_id: str, extension: str) -> str:
        """Upload a validated file and return the value to save as Document.storage_path."""
        self.client.upload_file(str(local_path), self.bucket, self.key_for(document_id, extension))
        return self.storage_path_for(document_id, extension)

    def delete(self, document_id: str, extension: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self.key_for(document_id, extension))
        except Exception:  # cleanup is best effort; never mask the original error
            pass

    def exists(self, document_id: str) -> bool:
        return self._find_key(document_id) is not None

    def resolve(self, document_id: str) -> Path:
        key = self._find_key(document_id)
        if key is None:
            raise DocumentNotFoundError(document_id)
        destination = Path(self._cache.name) / Path(key).name
        if not destination.exists():
            self.client.download_file(self.bucket, key, str(destination))
        return destination

    def _find_key(self, document_id: str) -> str | None:
        response = self.client.list_objects_v2(
            Bucket=self.bucket, Prefix=f"{POLICY_PREFIX}{document_id}.", MaxKeys=1
        )
        contents = response.get("Contents") or []
        return contents[0]["Key"] if contents else None


def get_policy_storage() -> "S3PolicyStorage | DocumentStorage":
    """S3 when S3_POLICY_BUCKET is set; otherwise the local policy_sources folder."""
    bucket = os.environ.get("S3_POLICY_BUCKET", "").strip()
    if bucket:
        return S3PolicyStorage(bucket)
    return DocumentStorage(str(DocumentStorage().base_dir / "policy_sources"))
