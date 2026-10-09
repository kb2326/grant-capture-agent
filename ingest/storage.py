"""Blob storage for raw attachments: local filesystem or Google Cloud Storage."""

import re
from pathlib import Path, PurePosixPath
from typing import Protocol

ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/html",
        "text/plain",
    }
)
_ALLOWED_SUFFIXES = frozenset({".pdf", ".docx", ".doc", ".html", ".htm", ".txt"})
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def is_allowed_attachment(mime: str | None, file_name: str) -> bool:
    if mime:
        return mime.split(";")[0].strip().lower() in ALLOWED_MIME_TYPES
    return PurePosixPath(file_name.lower()).suffix in _ALLOWED_SUFFIXES


def _clean(part: str) -> str:
    name = (
        PurePosixPath(part.replace("\\", "/")).name
        if "/" in part or "\\" in part
        else part
    )
    cleaned = _UNSAFE.sub("_", name).strip("._")
    return cleaned or "unnamed"


def safe_key(source: str, source_id: str, file_name: str) -> str:
    segments = [
        s for s in file_name.replace("\\", "/").split("/") if s not in ("", ".", "..")
    ]
    name = _clean("_".join(segments)) if segments else "unnamed"
    return f"raw/{_clean(source)}/{_clean(source_id)}/{name}"


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> str: ...
    def exists(self, key: str) -> bool: ...
    def get(self, key: str) -> bytes: ...
    def list(self, prefix: str) -> list[str]: ...


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError(f"key escapes blob root: {key}")
        return path

    def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.as_uri()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def list(self, prefix: str) -> list[str]:
        base = self._path(prefix.rsplit("/", 1)[0]) if "/" in prefix else self.root
        if not base.exists():
            return []
        keys = (
            f.relative_to(self.root).as_posix() for f in base.rglob("*") if f.is_file()
        )
        return sorted(k for k in keys if k.startswith(prefix))


class GCSBlobStore:
    def __init__(self, bucket: str, client=None) -> None:
        from google.cloud import storage

        self._client = client or storage.Client()
        self._bucket = self._client.bucket(bucket)
        self.bucket_name = bucket

    def put(self, key: str, data: bytes) -> str:
        self._bucket.blob(key).upload_from_string(data)
        return f"gs://{self.bucket_name}/{key}"

    def exists(self, key: str) -> bool:
        return self._bucket.blob(key).exists()

    def get(self, key: str) -> bytes:
        return self._bucket.blob(key).download_as_bytes()

    def list(self, prefix: str) -> list[str]:
        return sorted(
            b.name for b in self._client.list_blobs(self.bucket_name, prefix=prefix)
        )


def blob_store_from_root(root: str) -> BlobStore:
    if root.startswith("gs://"):
        return GCSBlobStore(root.removeprefix("gs://").split("/", 1)[0])
    return LocalBlobStore(Path(root))


def read_uri(uri: str) -> bytes:
    """Read a stored blob by the URI recorded in documents.gcs_uri."""
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    if uri.startswith("gs://"):
        from google.cloud import storage

        bucket, _, key = uri.removeprefix("gs://").partition("/")
        return storage.Client().bucket(bucket).blob(key).download_as_bytes()
    if uri.startswith("file:"):
        return Path(url2pathname(urlparse(uri).path)).read_bytes()
    return Path(uri).read_bytes()
