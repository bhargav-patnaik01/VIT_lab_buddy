from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow

ROLES = ("admin", "head", "incharge")
CAL_MODES = ("time", "usage", "both")
INSTRUMENT_STATUSES = ("active", "out_of_service", "retired")


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(16))  # admin | head | incharge
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    department: Mapped[Department | None] = relationship()


class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_tag: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(60), default="General")
    make: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    serial_no: Mapped[str] = mapped_column(String(80), default="")
    location: Mapped[str] = mapped_column(String(120), default="")
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    calibration_mode: Mapped[str] = mapped_column(String(8), default="time")  # time | usage | both
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    commissioned_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    department: Mapped[Department] = relationship()


class Calibration(Base):
    __tablename__ = "calibrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    performed_on: Mapped[date] = mapped_column(Date)
    performed_by: Mapped[str] = mapped_column(String(160), default="")  # agency / technician
    certificate_no: Mapped[str] = mapped_column(String(80), default="")
    result: Mapped[str] = mapped_column(String(12), default="pass")  # pass | adjusted | fail
    notes: Mapped[str] = mapped_column(Text, default="")
    certificate_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    certificate_filename: Mapped[str | None] = mapped_column(String(200), nullable=True)
    certificate_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    instrument: Mapped[Instrument] = relationship()


class UsageSession(Base):
    __tablename__ = "usage_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    user_ref: Mapped[str] = mapped_column(String(120), default="")  # who used it (reg no / name)
    purpose: Mapped[str] = mapped_column(String(200), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hours: Mapped[float | None] = mapped_column(Float, nullable=True)  # set when closed
    source: Mapped[str] = mapped_column(String(12), default="manual")  # manual | device

    instrument: Mapped[Instrument] = relationship()


class LabAccess(Base):
    __tablename__ = "lab_access"
    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    person_ref: Mapped[str] = mapped_column(String(120))
    card_uid: Mapped[str] = mapped_column(String(60), default="")
    direction: Mapped[str] = mapped_column(String(4))  # in | out
    method: Mapped[str] = mapped_column(String(12), default="manual")  # rfid | manual
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    department: Mapped[Department] = relationship()


class AuditLog(Base):
    """Append-only, hash-chained. Each row's hash covers the previous row's hash."""

    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    actor: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(40), default="")
    department_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


Index("ix_usage_instrument_started", UsageSession.instrument_id, UsageSession.started_at)
