from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .. import policy
from ..db import get_db, utcnow
from ..deps import current_user
from ..models import AuditLog, Department, Instrument, UsageSession, User
from ..schemas import AuditOut
from ..services import due
from .access import occupancy

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

STATUSES = ("ok", "due_soon", "overdue", "failed", "uncalibrated", "out_of_service")


@router.get("")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Instrument).options(joinedload(Instrument.department)).where(Instrument.status != "retired")
    f = policy.scope(user, Instrument.department_id)
    if f is not None:
        stmt = stmt.where(f)
    instruments = list(db.execute(stmt).scalars())
    infos = due.load_due(db, instruments)

    counts = {s: 0 for s in STATUSES}
    depts: dict[int, dict] = {}
    dq = select(Department).order_by(Department.name)
    df = policy.scope(user, Department.id)
    if df is not None:
        dq = dq.where(df)
    for d in db.execute(dq).scalars():
        depts[d.id] = {"department_id": d.id, "code": d.code, "name": d.name, "total": 0, **{s: 0 for s in STATUSES}}

    attention, upcoming = [], []
    today = due.today_local()
    for i in instruments:
        info = infos[i.id]
        counts[info.status] = counts.get(info.status, 0) + 1
        row = depts.get(i.department_id)
        if row is not None:
            row["total"] += 1
            row[info.status] = row.get(info.status, 0) + 1
        item = {
            "id": i.id, "asset_tag": i.asset_tag, "name": i.name, "department_code": i.department.code,
            "status": info.status, "reason": info.reason, "next_due_on": info.next_due_on,
            "days_remaining": info.days_remaining, "hours_remaining": info.hours_remaining,
        }
        if info.status in due.ATTENTION:
            attention.append(item)
        if info.next_due_on and 0 <= (info.next_due_on - today).days <= 60 and info.status not in ("out_of_service",):
            upcoming.append(item)

    rank = {"overdue": 0, "failed": 1, "uncalibrated": 2, "due_soon": 3}
    attention.sort(key=lambda x: (rank.get(x["status"], 9), x["days_remaining"] if x["days_remaining"] is not None else 9999))
    upcoming.sort(key=lambda x: x["next_due_on"])

    total = len(instruments)
    compliant = counts["ok"] + counts["due_soon"]  # still within calibration validity
    since = utcnow() - timedelta(days=30)
    uq = select(func.coalesce(func.sum(UsageSession.hours), 0.0)).join(Instrument).where(UsageSession.started_at >= since)
    if f is not None:
        uq = uq.where(f)
    in_use_q = select(func.count()).select_from(UsageSession).join(Instrument).where(UsageSession.ended_at.is_(None))
    if f is not None:
        in_use_q = in_use_q.where(f)
    labs = occupancy(db, user)

    aq = select(AuditLog).order_by(AuditLog.id.desc()).limit(8)
    af = policy.scope(user, AuditLog.department_id)
    if af is not None:
        aq = aq.where(af)

    return {
        "total": total,
        "counts": counts,
        "compliance_pct": round(100 * compliant / total, 1) if total else 100.0,
        "departments": list(depts.values()),
        "attention": attention[:10],
        "attention_total": len(attention),
        "upcoming": upcoming[:10],
        "usage_hours_30d": round(float(db.execute(uq).scalar_one()), 1),
        "in_use_now": db.execute(in_use_q).scalar_one(),
        "labs": labs,
        "inside_now": sum(len(l["inside"]) for l in labs),
        "entries_today": sum(l["entries_today"] for l in labs),
        "recent_activity": [AuditOut.model_validate(r).model_dump(mode="json") for r in db.execute(aq).scalars()],
    }
