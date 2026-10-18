from sqlalchemy import select

from app import bootstrap
from app.audit import verify_chain
from app.db import SessionLocal
from app.models import User


def test_bootstrap_creates_admin_only_on_empty_database(client, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET_ARN", "arn:aws:secretsmanager:test")
    monkeypatch.setattr(bootstrap, "_secret", lambda arn: {"email": "First@VIT.ac.in", "password": "S3cret-pass-123"})

    bootstrap.ensure_admin()  # fixture already seeded 4 users -> no-op
    with SessionLocal() as db:
        assert db.execute(select(User).where(User.email == "first@vit.ac.in")).scalar_one_or_none() is None

        for u in db.execute(select(User)).scalars().all():
            db.delete(u)
        db.commit()

    bootstrap.ensure_admin()
    with SessionLocal() as db:
        u = db.execute(select(User)).scalar_one()
        assert u.email == "first@vit.ac.in" and u.role == "admin" and u.password_hash.startswith("scrypt$")
        assert verify_chain(db)["ok"]

    bootstrap.ensure_admin()  # idempotent
    with SessionLocal() as db:
        assert len(db.execute(select(User)).scalars().all()) == 1
