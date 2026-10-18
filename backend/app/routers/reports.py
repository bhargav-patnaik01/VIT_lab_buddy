"""CSV exports for accreditation (NBA / NAAC) review, scoped to the caller's departments."""
import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import audit, policy
from ..db import get_db
from ..deps import current_user
from ..models import Calibration, Instrument, User
from ..services import due

router = APIRouter(prefix="/reports", tags=["reports"])


def _safe(v):
    """Neutralise spreadsheet formula injection."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _csv(rows: list[list], header: list[str], filename: str) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([_safe(c) for c in r])
    return Response(
        "﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/instruments.csv")
def instruments_csv(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Instrument).options(joinedload(Instrument.department)).order_by(Instrument.department_id, Instrument.asset_tag)
    f = policy.scope(user, Instrument.department_id)
    if f is not None:
        stmt = stmt.where(f)
    items = list(db.execute(stmt).scalars())
    infos = due.load_due(db, items)
    rows = []
    for i in items:
        d = infos[i.id]
        rows.append([i.department.code, i.asset_tag, i.name, i.category, i.make, i.model, i.serial_no, i.location, i.status,
                     i.calibration_mode, i.interval_days, i.interval_hours, d.last_calibrated_on, d.next_due_on, d.days_remaining,
                     d.usage_hours_since, d.hours_remaining, d.status, d.reason])
    audit.record(db, user.email, "report.export", "report", "instruments", None, {"rows": len(rows)})
    db.commit()
    return _csv(rows, ["Department", "Asset tag", "Instrument", "Category", "Make", "Model", "Serial no", "Location", "Instrument status",
                       "Calibration basis", "Interval (days)", "Interval (hours)", "Last calibrated", "Next due", "Days remaining",
                       "Hours used since calibration", "Hours remaining", "Calibration status", "Note"], "instrument-calibration-status.csv")


@router.get("/calibrations.csv")
def calibrations_csv(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = (
        select(Calibration).join(Instrument)
        .options(joinedload(Calibration.instrument).joinedload(Instrument.department))
        .order_by(Calibration.performed_on.desc(), Calibration.id.desc())
    )
    f = policy.scope(user, Instrument.department_id)
    if f is not None:
        stmt = stmt.where(f)
    rows = [
        [c.instrument.department.code, c.instrument.asset_tag, c.instrument.name, c.performed_on, c.result, c.performed_by,
         c.certificate_no, c.certificate_filename or "", c.certificate_sha256 or "", c.created_by, c.notes]
        for c in db.execute(stmt).scalars()
    ]
    audit.record(db, user.email, "report.export", "report", "calibrations", None, {"rows": len(rows)})
    db.commit()
    return _csv(rows, ["Department", "Asset tag", "Instrument", "Calibrated on", "Result", "Performed by", "Certificate no",
                       "Certificate file", "Certificate SHA-256", "Recorded by", "Notes"], "calibration-records.csv")
