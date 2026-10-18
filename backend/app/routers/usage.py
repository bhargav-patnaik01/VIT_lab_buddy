from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import audit, policy
from ..db import get_db, utcnow
from ..deps import current_user
from ..models import Instrument, UsageSession, User
from ..schemas import UsageManual, UsageOut, UsageStart
from ..services import usage as svc
from .instruments import get_instrument

router = APIRouter(tags=["usage"])


def usage_out(s: UsageSession) -> UsageOut:
    hours = s.hours if s.hours is not None else round((utcnow() - s.started_at).total_seconds() / 3600, 3)
    return UsageOut(
        id=s.id, instrument_id=s.instrument_id, asset_tag=s.instrument.asset_tag, instrument_name=s.instrument.name,
        department_code=s.instrument.department.code, user_ref=s.user_ref, purpose=s.purpose, started_at=s.started_at,
        ended_at=s.ended_at, hours=hours, source=s.source,
    )


def _load(stmt):
    return stmt.options(joinedload(UsageSession.instrument).joinedload(Instrument.department))


@router.get("/usage", response_model=list[UsageOut])
def recent(limit: int = 100, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = _load(select(UsageSession).join(Instrument)).order_by(UsageSession.started_at.desc()).limit(min(limit, 500))
    f = policy.scope(user, Instrument.department_id)
    if f is not None:
        stmt = stmt.where(f)
    return [usage_out(s) for s in db.execute(stmt).scalars()]


@router.get("/instruments/{inst_id}/usage")
def for_instrument(inst_id: int, days: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inst = get_instrument(db, inst_id, user)
    days = max(1, min(days, 365))
    since = utcnow() - timedelta(days=days)
    rows = db.execute(
        _load(select(UsageSession)).where(UsageSession.instrument_id == inst.id, UsageSession.started_at >= since).order_by(UsageSession.started_at.desc())
    ).scalars().all()
    per_day: dict[str, float] = defaultdict(float)
    for s in rows:
        h = s.hours if s.hours is not None else (utcnow() - s.started_at).total_seconds() / 3600
        per_day[s.started_at.date().isoformat()] += h
    daily = []
    for n in range(days):
        d = (utcnow() - timedelta(days=days - 1 - n)).date().isoformat()
        daily.append({"date": d, "hours": round(per_day.get(d, 0.0), 2)})
    return {"sessions": [usage_out(s) for s in rows[:100]], "daily": daily, "total_hours": round(sum(per_day.values()), 2)}


@router.post("/instruments/{inst_id}/usage/start", response_model=UsageOut, status_code=201)
def start(inst_id: int, body: UsageStart, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inst = get_instrument(db, inst_id, user, write=True)
    s = svc.start(db, inst, body.user_ref, body.purpose, user.email)
    db.commit()
    return usage_out(db.execute(_load(select(UsageSession)).where(UsageSession.id == s.id)).scalar_one())


@router.post("/instruments/{inst_id}/usage/stop", response_model=UsageOut)
def stop(inst_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inst = get_instrument(db, inst_id, user, write=True)
    s = svc.stop(db, inst, user.email)
    db.commit()
    return usage_out(db.execute(_load(select(UsageSession)).where(UsageSession.id == s.id)).scalar_one())


@router.post("/instruments/{inst_id}/usage", response_model=UsageOut, status_code=201)
def log_manual(inst_id: int, body: UsageManual, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inst = get_instrument(db, inst_id, user, write=True)
    started = body.started_at
    if started.tzinfo is not None:
        started = started.astimezone(timezone.utc).replace(tzinfo=None)
    if started > utcnow() + timedelta(minutes=5):
        raise HTTPException(422, "Start time cannot be in the future")
    s = UsageSession(
        instrument_id=inst.id, user_ref=body.user_ref.strip(), purpose=body.purpose.strip(), started_at=started,
        ended_at=started + timedelta(hours=body.hours), hours=body.hours, source="manual",
    )
    db.add(s)
    db.flush()
    audit.record(db, user.email, "usage.log", "instrument", inst.id, inst.department_id, {"asset_tag": inst.asset_tag, "hours": body.hours, "user": s.user_ref})
    db.commit()
    return usage_out(db.execute(_load(select(UsageSession)).where(UsageSession.id == s.id)).scalar_one())
