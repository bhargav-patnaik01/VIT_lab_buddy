"""Certificate storage: local disk for development, Amazon S3 on AWS."""
from pathlib import Path

from .config import get_settings
from .security import decode_token, make_token


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("bad key")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def url(self, key: str, filename: str, ttl: int = 300) -> str:
        return "/api/files/" + make_token({"key": key, "fn": filename}, minutes=ttl / 60)

    def read_token(self, token: str) -> tuple[Path, str]:
        c = decode_token(token)
        return self._path(c["key"]), c.get("fn", "certificate")


class S3Storage:
    def __init__(self, bucket: str):
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3")

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    def url(self, key: str, filename: str, ttl: int = 300) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket, "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=ttl,
        )


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage(s.s3_bucket) if s.storage_backend == "s3" else LocalStorage(s.local_storage_dir)
    return _storage
