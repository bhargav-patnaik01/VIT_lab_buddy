"""Runtime configuration, read from environment variables.

Local development needs no configuration at all (SQLite + local disk).
On AWS the same code is driven purely by env vars set in infra/template.yaml:
RDS credentials and the JWT secret come from Secrets Manager, certificates go
to S3 and due-date digests go to SNS.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _secret(arn: str) -> dict | str:
    import boto3  # provided by the Lambda runtime; only needed on AWS

    raw = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
    try:
        return json.loads(raw)
    except ValueError:
        return raw


class Settings:
    env = _env("CAD_ENV", "local")  # local | aws
    tz = _env("CAD_TIMEZONE", "Asia/Kolkata")
    token_hours = int(_env("CAD_TOKEN_HOURS", "12"))

    storage_backend = _env("STORAGE_BACKEND", "local")  # local | s3
    s3_bucket = _env("S3_BUCKET")
    local_storage_dir = Path(_env("LOCAL_STORAGE_DIR", str(BASE_DIR / "data" / "files")))
    max_upload_bytes = int(_env("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))  # API GW / Lambda payload friendly

    sns_topic_arn = _env("SNS_TOPIC_ARN")
    device_api_key = _env("DEVICE_API_KEY", "dev-device-key")
    cors_origins = [o for o in _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o]
    frontend_dist = Path(_env("FRONTEND_DIST", str(BASE_DIR.parent / "frontend" / "dist")))

    due_soon_days = int(_env("DUE_SOON_DAYS", "30"))
    due_soon_usage_fraction = float(_env("DUE_SOON_USAGE_FRACTION", "0.10"))

    @property
    def database_url(self) -> str:
        if _env("DATABASE_URL"):
            return _env("DATABASE_URL")
        if _env("DB_SECRET_ARN"):  # RDS PostgreSQL, credentials in Secrets Manager
            s = _secret(_env("DB_SECRET_ARN"))
            host = _env("DB_HOST") or s.get("host", "")
            port = _env("DB_PORT", str(s.get("port", 5432)))
            name = _env("DB_NAME", s.get("dbname", "cad"))
            from urllib.parse import quote_plus

            return f"postgresql+pg8000://{quote_plus(s['username'])}:{quote_plus(s['password'])}@{host}:{port}/{name}"
        data = BASE_DIR / "data"
        data.mkdir(exist_ok=True)
        return f"sqlite:///{(data / 'cad.db').as_posix()}"

    @property
    def jwt_secret(self) -> str:
        if _env("JWT_SECRET"):
            return _env("JWT_SECRET")
        if _env("JWT_SECRET_ARN"):
            s = _secret(_env("JWT_SECRET_ARN"))
            return s["secret"] if isinstance(s, dict) else s
        if self.env != "local":
            raise RuntimeError("JWT_SECRET or JWT_SECRET_ARN must be set outside local mode")
        return "local-dev-secret-not-for-production-use"


@lru_cache
def get_settings() -> Settings:
    return Settings()
