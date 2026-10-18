from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import audit, policy
from ..db import get_db, utcnow
from ..deps import current_user
from ..models import Department, LabAccess, User
from ..schemas import AccessIn, AccessOut
from ..services.due import start_of_today_utc

router = APIRouter(prefix="/access", tags=["lab access"])

INSIDE_WINDOW = timedelta(hours=12)  # an "in" swipe older than this is assumed stale (forgot to swipe out)


def access_out(a: LabAccess) -> AccessOut:
    return AccessOut(
        id=a.id, department_id=a.department_id, department_code=a.department.code, person_ref=a.person_ref,
        card_uid=a.card_uid, direction=a.direction, method=a.method, at=a.at,
    )


def add_event(db: Session, dept: Department, person_ref: str, direction: str, method: str, card_uid: str, actor: str, at: datetime | None = None) -> LabAccess:
    if at is not None and at.tzinfo is not None:
        at = at.astimezone(timezone.utc).replace(tzinfo=None)
    a = LabAccess(department_id=dept.id, person_ref=person_ref.strip(), card_uid=card_uid.strip(), direction=direction, method=method, at=at or utcnow())
    db.add(a)
    db.flush()
    audit.record(db, actor, "access." + direction, "lab", dept.id, dept.id, {"person": a.person_ref, "method": method})
    return a


@router.get("", response_model=list[AccessOut])
def list_events(department_id: int | None = None, days: int = 7, limit: int = 300, user: User = Depends(current_user), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=max(1, min(days, 90)))
    stmt = select(LabAccess).options(joinedload(LabAccess.department)).where(LabAccess.at >= since).order_by(LabAccess.at.desc()).limit(min(limit, 1000))
    f = policy.scope(user, LabAccess.department_id)
    if f is not None:
        stmt = stmt.where(f)
    if department_id:
        stmt = stmt.where(LabAccess.department_id == department_id)
    return [access_out(a) for a in db.execute(stmt).scalars()]


@router.get("/summary")
def summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Per-lab occupancy right now + swipes today."""
    return occupancy(db, user)


def occupancy(db: Session, user: User) -> list[dict]:
    dq = select(Department).order_by(Department.name)
    f = policy.scope(user, Department.id)
    if f is not None:
        dq = dq.where(f)
    depts = db.execute(dq).scalars().all()
    now = utcnow()
    start_today = start_of_today_utc()
    events = db.execute(
        select(LabAccess).where(LabAccess.department_id.in_([d.id for d in depts]), LabAccess.at >= now - INSIDE_WINDOW).order_by(LabAccess.at)
    ).scalars().all() if depts else []
    latest: dict[tuple[int, str], LabAccess] = {}
    for e in events:
        latest[(e.department_id, e.person_ref)] = e
    today_counts = {d.id: 0 for d in depts}
    for e in db.execute(select(LabAccess).where(LabAccess.department_id.in_([d.id for d in depts]), LabAccess.at >= start_today, LabAccess.direction == "in")).scalars() if depts else []:
        today_counts[e.department_id] += 1
    return [
        {
            "department_id": d.id, "code": d.code, "name": d.name,
            "inside": sorted(p for (did, p), e in latest.items() if did == d.id and e.direction == "in"),
            "entries_today": today_counts[d.id],
        }
        for d in depts
    ]


@router.post("", response_model=AccessOut, status_code=201)
def log_event(body: AccessIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    policy.require_write(user, body.department_id)
    dept = db.get(Department, body.department_id)
    if not dept:
        raise HTTPException(422, "Unknown department")
    a = add_event(db, dept, body.person_ref, body.direction, body.method, body.card_uid, user.email)
    db.commit()
    return access_out(db.execute(select(LabAccess).options(joinedload(LabAccess.department)).where(LabAccess.id == a.id)).scalar_one())
