from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import audit, policy
from ..db import get_db
from ..deps import current_user
from ..models import Department, Instrument, UsageSession, User
from ..schemas import DueOut, InstrumentIn, InstrumentOut, InstrumentUpdate
from ..services import due

router = APIRouter(prefix="/instruments", tags=["instruments"])


def build_out(db: Session, instruments: list[Instrument]) -> list[InstrumentOut]:
    infos = due.load_due(db, instruments)
    open_by_inst = {}
    if instruments:
        rows = db.execute(
            select(UsageSession).where(UsageSession.instrument_id.in_([i.id for i in instruments]), UsageSession.ended_at.is_(None))
        ).scalars()
        open_by_inst = {s.instrument_id: s for s in rows}
    out = []
    for i in instruments:
        d = infos[i.id]
        s = open_by_inst.get(i.id)
        out.append(InstrumentOut(
            id=i.id, asset_tag=i.asset_tag, name=i.name, category=i.category, make=i.make, model=i.model,
            serial_no=i.serial_no, location=i.location, department_id=i.department_id, department_code=i.department.code,
            status=i.status, calibration_mode=i.calibration_mode, interval_days=i.interval_days,
            interval_hours=i.interval_hours, commissioned_on=i.commissioned_on, notes=i.notes,
            due=DueOut(**d.__dict__), in_use=s is not None, in_use_by=s.user_ref if s else None,
        ))
    return out


def get_instrument(db: Session, inst_id: int, user: User, write: bool = False) -> Instrument:
    inst = db.execute(select(Instrument).options(joinedload(Instrument.department)).where(Instrument.id == inst_id)).scalar_one_or_none()
    if not inst:
        raise HTTPException(404, "Not found")
    (policy.require_write if write else policy.require_read)(user, inst.department_id)
    return inst


def _validate_intervals(mode: str, days, hours):
    if mode in ("time", "both") and not days:
        raise HTTPException(422, "Set a calibration interval in days for time-based calibration")
    if mode in ("usage", "both") and not hours:
        raise HTTPException(422, "Set a usage-hours limit for usage-based calibration")


@router.get("", response_model=list[InstrumentOut])
def list_instruments(
    q: str = "", department_id: int | None = None, status: str = "", category: str = "",
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    stmt = select(Instrument).options(joinedload(Instrument.department)).order_by(Instrument.asset_tag)
    f = policy.scope(user, Instrument.department_id)
    if f is not None:
        stmt = stmt.where(f)
    if department_id:
        stmt = stmt.where(Instrument.department_id == department_id)
    if category:
        stmt = stmt.where(Instrument.category == category)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Instrument.name.ilike(like), Instrument.asset_tag.ilike(like), Instrument.serial_no.ilike(like), Instrument.make.ilike(like), Instrument.model.ilike(like)))
    items = build_out(db, list(db.execute(stmt).scalars()))
    if status:
        wanted = set(status.split(","))
        items = [i for i in items if i.due.status in wanted or (i.status in wanted)]
    return items


@router.get("/categories", response_model=list[str])
def categories(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Instrument.category).distinct().order_by(Instrument.category)
    f = policy.scope(user, Instrument.department_id)
    if f is not None:
        stmt = stmt.where(f)
    return list(db.execute(stmt).scalars())


@router.get("/{inst_id}", response_model=InstrumentOut)
def get_one(inst_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return build_out(db, [get_instrument(db, inst_id, user)])[0]


@router.post("", response_model=InstrumentOut, status_code=201)
def create(body: InstrumentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    policy.require_write(user, body.department_id)
    if not db.get(Department, body.department_id):
        raise HTTPException(422, "Unknown department")
    _validate_intervals(body.calibration_mode, body.interval_days, body.interval_hours)
    data = body.model_dump()
    data["asset_tag"] = data["asset_tag"].strip().upper()
    inst = Instrument(**data)
    db.add(inst)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Asset tag {data['asset_tag']} is already in use")
    audit.record(db, user.email, "instrument.create", "instrument", inst.id, inst.department_id, {"asset_tag": inst.asset_tag, "name": inst.name})
    db.commit()
    return build_out(db, [get_instrument(db, inst.id, user)])[0]


@router.put("/{inst_id}", response_model=InstrumentOut)
def update(inst_id: int, body: InstrumentUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inst = get_instrument(db, inst_id, user, write=True)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is None and k in ("name", "category", "status", "calibration_mode"):
            continue
        setattr(inst, k, v)
    _validate_intervals(inst.calibration_mode, inst.interval_days, inst.interval_hours)
    audit.record(db, user.email, "instrument.update", "instrument", inst.id, inst.department_id, {"asset_tag": inst.asset_tag, "changed": sorted(data)})
    db.commit()
    return build_out(db, [inst])[0]
