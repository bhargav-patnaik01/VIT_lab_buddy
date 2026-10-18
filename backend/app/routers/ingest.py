"""Device-facing endpoints for RFID readers and bench-instrument controllers (authenticated with X-Device-Key)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import device_key
from ..models import Department, Instrument
from ..schemas import IngestAccess, IngestUsage
from ..services import usage as usage_svc
from .access import add_event

router = APIRouter(prefix="/ingest", tags=["device ingest"])


@router.post("/access", status_code=201)
def ingest_access(body: IngestAccess, actor: str = Depends(device_key), db: Session = Depends(get_db)):
    dept = db.execute(select(Department).where(Department.code == body.dept_code.upper())).scalar_one_or_none()
    if not dept:
        raise HTTPException(404, "Unknown department code")
    a = add_event(db, dept, body.person_ref, body.direction, "rfid", body.card_uid, "device:rfid", body.at)
    db.commit()
    return {"id": a.id}


@router.post("/usage", status_code=201)
def ingest_usage(body: IngestUsage, actor: str = Depends(device_key), db: Session = Depends(get_db)):
    inst = db.execute(select(Instrument).where(Instrument.asset_tag == body.asset_tag.upper())).scalar_one_or_none()
    if not inst:
        raise HTTPException(404, "Unknown asset tag")
    if body.event == "start":
        s = usage_svc.start(db, inst, body.user_ref, "", "device:controller", "device", body.at)
    else:
        s = usage_svc.stop(db, inst, "device:controller", body.at)
    db.commit()
    return {"id": s.id, "hours": s.hours}
