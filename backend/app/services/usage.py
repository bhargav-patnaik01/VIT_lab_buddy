from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import utcnow
from ..models import Instrument, UsageSession


def _naive_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return utcnow()
    if dt.tzinfo is not None:
        from datetime import timezone

        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def open_session(db: Session, inst_id: int) -> UsageSession | None:
    return db.execute(
        select(UsageSession).where(UsageSession.instrument_id == inst_id, UsageSession.ended_at.is_(None))
    ).scalars().first()


def start(db: Session, inst: Instrument, user_ref: str, purpose: str, actor: str, source: str = "manual", at: datetime | None = None) -> UsageSession:
    if inst.status != "active":
        raise HTTPException(409, "Instrument is not active")
    if open_session(db, inst.id):
        raise HTTPException(409, "Instrument already has a running session")
    s = UsageSession(instrument_id=inst.id, user_ref=user_ref.strip(), purpose=purpose.strip(), started_at=_naive_utc(at), source=source)
    db.add(s)
    db.flush()
    audit.record(db, actor, "usage.start", "instrument", inst.id, inst.department_id, {"asset_tag": inst.asset_tag, "user": s.user_ref, "source": source})
    return s


def stop(db: Session, inst: Instrument, actor: str, at: datetime | None = None) -> UsageSession:
    s = open_session(db, inst.id)
    if not s:
        raise HTTPException(409, "No running session for this instrument")
    end = _naive_utc(at)
    if end < s.started_at:
        end = s.started_at
    s.ended_at = end
    s.hours = round((end - s.started_at).total_seconds() / 3600, 3)
    audit.record(db, actor, "usage.stop", "instrument", inst.id, inst.department_id, {"asset_tag": inst.asset_tag, "hours": s.hours})
    return s
