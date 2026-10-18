"""First-run bootstrap for a fresh production database (no demo data is ever loaded on AWS).

If BOOTSTRAP_ADMIN_SECRET_ARN is set and the users table is empty, create one administrator from that
Secrets Manager secret ({"email": ..., "password": ...}). Rotate the password after the first sign-in.
"""
import logging
import os

from sqlalchemy import select

from . import audit
from .config import _secret
from .db import SessionLocal
from .models import User
from .security import hash_password

log = logging.getLogger("cad.bootstrap")


def ensure_admin() -> None:
    arn = os.environ.get("BOOTSTRAP_ADMIN_SECRET_ARN")
    if not arn:
        return
    with SessionLocal() as db:
        if db.execute(select(User.id).limit(1)).first():
            return
        s = _secret(arn)
        user = User(email=s["email"].strip().lower(), name="Administrator", role="admin", password_hash=hash_password(s["password"]))
        db.add(user)
        db.flush()
        audit.record(db, "system", "user.create", "user", user.id, None, {"email": user.email, "role": "admin", "bootstrap": True})
        db.commit()
        log.warning("Bootstrap administrator created: %s", user.email)
