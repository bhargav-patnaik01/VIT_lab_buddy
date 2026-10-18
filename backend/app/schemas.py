from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator


def _utc(d: datetime) -> str:
    return d.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


UTC = Annotated[datetime, PlainSerializer(_utc, return_type=str)]
Role = Literal["admin", "head", "incharge"]
CalMode = Literal["time", "usage", "both"]
InstStatus = Literal["active", "out_of_service", "retired"]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth / users / departments
class LoginIn(BaseModel):
    email: str
    password: str


class DepartmentIn(BaseModel):
    code: str = Field(min_length=2, max_length=16)
    name: str = Field(min_length=2, max_length=120)


class DepartmentOut(Out):
    id: int
    code: str
    name: str


class UserOut(Out):
    id: int
    email: str
    name: str
    role: Role
    department_id: int | None
    department_code: str | None = None
    active: bool


class UserIn(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    name: str = Field(min_length=2, max_length=120)
    role: Role
    department_id: int | None = None
    password: str = Field(min_length=8, max_length=100)


class UserUpdate(BaseModel):
    name: str | None = None
    role: Role | None = None
    department_id: int | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=100)


class LoginOut(BaseModel):
    token: str
    user: UserOut


# ---- instruments
class InstrumentIn(BaseModel):
    asset_tag: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(default="General", max_length=60)
    make: str = ""
    model: str = ""
    serial_no: str = ""
    location: str = ""
    department_id: int
    status: InstStatus = "active"
    calibration_mode: CalMode = "time"
    interval_days: int | None = Field(default=365, ge=1, le=3650)
    interval_hours: float | None = Field(default=None, gt=0)
    commissioned_on: date | None = None
    notes: str = ""

    @field_validator("interval_days", "interval_hours", mode="before")
    @classmethod
    def _blank_none(cls, v):
        return None if v == "" else v


class InstrumentUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    make: str | None = None
    model: str | None = None
    serial_no: str | None = None
    location: str | None = None
    status: InstStatus | None = None
    calibration_mode: CalMode | None = None
    interval_days: int | None = None
    interval_hours: float | None = None
    commissioned_on: date | None = None
    notes: str | None = None


class DueOut(BaseModel):
    status: str
    last_calibrated_on: date | None
    next_due_on: date | None
    days_remaining: int | None
    usage_hours_since: float
    hours_remaining: float | None
    reason: str


class InstrumentOut(Out):
    id: int
    asset_tag: str
    name: str
    category: str
    make: str
    model: str
    serial_no: str
    location: str
    department_id: int
    department_code: str
    status: str
    calibration_mode: str
    interval_days: int | None
    interval_hours: float | None
    commissioned_on: date | None
    notes: str
    due: DueOut
    in_use: bool = False
    in_use_by: str | None = None


# ---- calibrations
class CalibrationOut(Out):
    id: int
    instrument_id: int
    asset_tag: str | None = None
    instrument_name: str | None = None
    department_code: str | None = None
    performed_on: date
    performed_by: str
    certificate_no: str
    result: str
    notes: str
    has_certificate: bool
    certificate_filename: str | None
    certificate_sha256: str | None
    created_by: str
    created_at: UTC


# ---- usage / access
class UsageStart(BaseModel):
    user_ref: str = Field(min_length=1, max_length=120)
    purpose: str = Field(default="", max_length=200)


class UsageManual(BaseModel):
    user_ref: str = Field(min_length=1, max_length=120)
    purpose: str = Field(default="", max_length=200)
    started_at: datetime
    hours: float = Field(gt=0, le=240)


class UsageOut(Out):
    id: int
    instrument_id: int
    asset_tag: str | None = None
    instrument_name: str | None = None
    department_code: str | None = None
    user_ref: str
    purpose: str
    started_at: UTC
    ended_at: UTC | None
    hours: float | None
    source: str


class AccessIn(BaseModel):
    department_id: int
    person_ref: str = Field(min_length=1, max_length=120)
    direction: Literal["in", "out"]
    card_uid: str = ""
    method: Literal["rfid", "manual"] = "manual"


class AccessOut(Out):
    id: int
    department_id: int
    department_code: str
    person_ref: str
    card_uid: str
    direction: str
    method: str
    at: UTC


class AuditOut(Out):
    id: int
    ts: UTC
    actor: str
    action: str
    entity: str
    entity_id: str
    department_id: int | None
    detail: str
    hash: str


# ---- device ingest (RFID readers, bench-instrument controllers)
class IngestAccess(BaseModel):
    dept_code: str
    person_ref: str
    direction: Literal["in", "out"]
    card_uid: str = ""
    at: datetime | None = None


class IngestUsage(BaseModel):
    asset_tag: str
    event: Literal["start", "stop"]
    user_ref: str = "device"
    at: datetime | None = None
