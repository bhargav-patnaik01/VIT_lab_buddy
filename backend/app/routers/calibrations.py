import hashlib
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import audit, policy
from ..config import get_settings
from ..db import get_db
from ..deps import current_user
from ..models import Calibration, Instrument, User
from ..schemas import CalibrationOut
from ..services.due import today_local
from ..storage import LocalStorage, get_storage
from .instruments import get_instrument

router = APIRouter(tags=["calibrations"])

ALLOWED = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
MAGIC = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}


def cal_out(c: Calibration) -> CalibrationOut:
    return CalibrationOut(
        id=c.id, instrument_id=c.instrument_id, asset_tag=c.instrument.asset_tag, instrument_name=c.instrument.name,
        department_code=c.instrument.department.code, performed_on=c.performed_on, performed_by=c.performed_by,
        certificate_no=c.certificate_no, result=c.result, notes=c.notes, has_certificate=bool(c.certificate_key),
        certificate_filename=c.certificate_filename, certificate_sha256=c.certificate_sha256,
        created_by=c.created_by, created_at=c.created_at,
    )


def _load(stmt):
    return stmt.options(joinedload(Calibration.instrument).joinedload(Instrument.department))


@router.get("/calibrations", response_model=list[CalibrationOut])
def list_all(limit: int = 200, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = _load(select(Calibration).join(Instrument)).order_by(Calibration.performed_on.desc(), Calibration.id.desc()).limit(min(limit, 1000))
    f = policy.scope(user, Instrument.department_id)
    if f is not None:
        stmt = stmt.where(f)
    return [cal_out(c) for c in db.execute(stmt).scalars()]


@router.get("/instruments/{inst_id}/calibrations", response_model=list[CalibrationOut])
def list_for_instrument(inst_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    get_instrument(db, inst_id, user)
    stmt = _load(select(Calibration)).where(Calibration.instrument_id == inst_id).order_by(Calibration.performed_on.desc(), Calibration.id.desc())
    return [cal_out(c) for c in db.execute(stmt).scalars()]


@router.post("/instruments/{inst_id}/calibrations", response_model=CalibrationOut, status_code=201)
async def record_calibration(
    inst_id: int,
    performed_on: date = Form(...),
    performed_by: str = Form(""),
    certificate_no: str = Form(""),
    result: str = Form("pass"),
    notes: str = Form(""),
    certificate: UploadFile | None = File(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    inst = get_instrument(db, inst_id, user, write=True)
    if result not in ("pass", "adjusted", "fail"):
        raise HTTPException(422, "Result must be pass, adjusted or fail")
    if performed_on > today_local() + timedelta(days=1):
        raise HTTPException(422, "Calibration date cannot be in the future")

    key = fname = digest = None
    if certificate is not None and certificate.filename:
        ext = Path(certificate.filename).suffix.lower()
        if ext not in ALLOWED:
            raise HTTPException(422, "Certificate must be a PDF, PNG or JPG file")
        data = await certificate.read(get_settings().max_upload_bytes + 1)
        if len(data) > get_settings().max_upload_bytes:
            raise HTTPException(413, f"Certificate exceeds {get_settings().max_upload_bytes // (1024 * 1024)} MB")
        if not data.startswith(MAGIC[ext]):
            raise HTTPException(422, "File content does not match its extension")
        digest = hashlib.sha256(data).hexdigest()
        key = f"certificates/{inst.department.code}/{inst.asset_tag}/{uuid.uuid4().hex}{ext}"
        fname = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(certificate.filename).name)[:150]
        get_storage().put(key, data, ALLOWED[ext])

    cal = Calibration(
        instrument_id=inst.id, performed_on=performed_on, performed_by=performed_by.strip()[:160],
        certificate_no=certificate_no.strip()[:80], result=result, notes=notes.strip(),
        certificate_key=key, certificate_filename=fname, certificate_sha256=digest, created_by=user.email,
    )
    db.add(cal)
    db.flush()
    audit.record(db, user.email, "calibration.record", "calibration", cal.id, inst.department_id,
                 {"asset_tag": inst.asset_tag, "performed_on": performed_on, "result": result, "certificate_sha256": digest})
    db.commit()
    cal = db.execute(_load(select(Calibration)).where(Calibration.id == cal.id)).scalar_one()
    return cal_out(cal)


@router.get("/calibrations/{cal_id}/certificate-url")
def certificate_url(cal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cal = db.execute(_load(select(Calibration)).where(Calibration.id == cal_id)).scalar_one_or_none()
    if not cal:
        raise HTTPException(404, "Not found")
    policy.require_read(user, cal.instrument.department_id)
    if not cal.certificate_key:
        raise HTTPException(404, "No certificate was uploaded for this calibration")
    audit.record(db, user.email, "certificate.view", "calibration", cal.id, cal.instrument.department_id, {"asset_tag": cal.instrument.asset_tag})
    db.commit()
    return {"url": get_storage().url(cal.certificate_key, cal.certificate_filename or "certificate"), "filename": cal.certificate_filename}


@router.get("/files/{token}", include_in_schema=False)
def local_file(token: str):
    """Local-dev equivalent of an S3 presigned URL: short-lived signed token, no auth header needed."""
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(404, "Not found")
    try:
        path, filename = storage.read_token(token)
    except Exception:
        raise HTTPException(403, "Link expired")
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path, filename=filename)
