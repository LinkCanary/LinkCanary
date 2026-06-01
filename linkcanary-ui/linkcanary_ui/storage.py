"""Report storage abstraction.

Two backends:
- ``local``: files live on the filesystem under ``settings.crawls_dir``.
- ``s3``: files live in an S3-compatible bucket (AWS S3 or Cloudflare R2).

Stored report references are *keys* (e.g. ``"<crawl_id>/report.csv"``). The link
checker writes plain local files; this layer publishes them to the backend and,
on read, materializes them back to a local path so existing ``open()``/
``FileResponse`` call sites keep working unchanged.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from .config import settings


class BaseStorage:
    def put_file(self, key: str, local_path: str) -> str:
        """Publish a local file under ``key`` and return the stored key."""
        raise NotImplementedError

    def localize(self, key: str) -> str:
        """Return a local filesystem path for reading the object at ``key``."""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalStorage(BaseStorage):
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _abs(self, key: str) -> str:
        # Back-compat: older rows stored absolute paths directly.
        if os.path.isabs(key):
            return key
        return str(self.root / key)

    def put_file(self, key: str, local_path: str) -> str:
        dest = Path(self._abs(key))
        dest.parent.mkdir(parents=True, exist_ok=True)
        if Path(local_path).resolve() != dest.resolve():
            shutil.copyfile(local_path, dest)
        return key

    def localize(self, key: str) -> str:
        return self._abs(key)

    def exists(self, key: str) -> bool:
        return os.path.exists(self._abs(key))


class S3Storage(BaseStorage):
    def __init__(self) -> None:
        import boto3  # lazy: only needed when the s3 backend is selected

        if not settings.s3_bucket:
            raise RuntimeError("storage_backend=s3 requires LINKCANARY_S3_BUCKET")

        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix or ""
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def _full_key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def put_file(self, key: str, local_path: str) -> str:
        self.client.upload_file(local_path, self.bucket, self._full_key(key))
        return key

    def localize(self, key: str) -> str:
        suffix = Path(key).suffix
        fd, tmp = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self.client.download_file(self.bucket, self._full_key(key), tmp)
        return tmp

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=self._full_key(key))
            return True
        except ClientError:
            return False


_storage: Optional[BaseStorage] = None


def get_storage() -> BaseStorage:
    """Return the process-wide storage backend (lazily constructed)."""
    global _storage
    if _storage is None:
        if settings.storage_backend == "s3":
            _storage = S3Storage()
        else:
            _storage = LocalStorage(settings.crawls_dir)
    return _storage
