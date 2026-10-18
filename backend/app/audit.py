"""Tamper-evident audit trail: an append-only hash chain.

hash = SHA256(prev_hash | ts | actor | action | entity | entity_id | department_id | detail)
Editing or deleting any past row breaks every hash after it; `verify_chain` finds the first break.
"""
import hashlib
import json
import threading
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import utcnow
from .models import AuditLog

GENESIS = "0" * 64
_lock = threading.Lock()


def _digest(prev: str, ts: datetime, actor: str, action: str, entity: str, entity_id: str, dept: int | None, detail: str) -> str:
    payload = "|".join([prev, ts.isoformat(timespec="microseconds"), actor, action, entity, entity_id, "" if dept is None else str(dept), detail])
    return hashlib.sha256(payload.encode()).hexdigest()


def record(
    db: Session,
    actor: str,
    action: str,
    entity: str,
    entity_id: str | int = "",
    department_id: int | None = None,
    detail: dict | str | None = None,
    ts: datetime | None = None,
) -> AuditLog:
    """Append one entry. Caller commits (so the entry lands atomically with the change it describes)."""
    detail_s = detail if isinstance(detail, str) else json.dumps(detail or {}, sort_keys=True, default=str)
    with _lock:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(727001)"))  # serialize chain writers across Lambda containers
        last = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
        prev = last.hash if last else GENESIS
        ts = ts or utcnow()
        row = AuditLog(
            ts=ts, actor=actor, action=action, entity=entity, entity_id=str(entity_id),
            department_id=department_id, detail=detail_s, prev_hash=prev,
            hash=_digest(prev, ts, actor, action, entity, str(entity_id), department_id, detail_s),
        )
        db.add(row)
        db.flush()
        return row


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        expected = _digest(prev, row.ts, row.actor, row.action, row.entity, row.entity_id, row.department_id, row.detail)
        if row.prev_hash != prev or row.hash != expected:
            return {"ok": False, "checked": count, "broken_at": row.id}
        prev = row.hash
        count += 1
    return {"ok": True, "checked": count, "broken_at": None}
