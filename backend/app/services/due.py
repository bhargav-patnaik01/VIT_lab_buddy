"""Calibration due-date logic (the "Lambda" piece of the design).

`evaluate` is a pure function so it behaves identically inside the API, the
scheduled scan Lambda and the unit tests. An instrument can be calibrated on a
time interval, a usage-hours interval, or whichever comes first ("both").
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import utcnow
from ..models import Calibration, Instrument, UsageSession

ATTENTION = ("overdue", "failed", "uncalibrated", "due_soon")


@dataclass
class DueInfo:
    status: str  # ok | due_soon | overdue | failed | uncalibrated | retired | out_of_service
    last_calibrated_on: date | None = None
    next_due_on: date | None = None
    days_remaining: int | None = None
    usage_hours_since: float = 0.0
    hours_remaining: float | None = None
    reason: str = ""


def today_local() -> date:
    return datetime.now(ZoneInfo(get_settings().tz)).date()


def start_of_today_utc() -> datetime:
    """Local midnight (institute timezone) as a naive UTC datetime, for 'today' queries."""
    from datetime import timezone

    local = datetime.now(ZoneInfo(get_settings().tz)).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def evaluate(
    inst: Instrument,
    last_cal: Calibration | None,
    usage_hours_since: float,
    today: date,
    due_soon_days: int | None = None,
    usage_fraction: float | None = None,
) -> DueInfo:
    s = get_settings()
    due_soon_days = s.due_soon_days if due_soon_days is None else due_soon_days
    usage_fraction = s.due_soon_usage_fraction if usage_fraction is None else usage_fraction

    if inst.status == "retired":
        return DueInfo("retired", reason="Instrument retired")
    info = DueInfo("ok", usage_hours_since=round(usage_hours_since, 2))
    if inst.status == "out_of_service":
        info.status, info.reason = "out_of_service", "Out of service"
    if last_cal is None:
        if info.status == "ok":
            info.status, info.reason = "uncalibrated", "No calibration on record"
        return info

    info.last_calibrated_on = last_cal.performed_on
    if last_cal.result == "fail" and info.status == "ok":
        info.status, info.reason = "failed", "Last calibration failed"

    use_time = inst.calibration_mode in ("time", "both") and inst.interval_days
    use_hours = inst.calibration_mode in ("usage", "both") and inst.interval_hours

    time_state, hours_state, reasons = "ok", "ok", []
    if use_time:
        info.next_due_on = last_cal.performed_on + timedelta(days=int(inst.interval_days))
        info.days_remaining = (info.next_due_on - today).days
        if info.days_remaining < 0:
            time_state = "overdue"
            reasons.append(f"{-info.days_remaining} days past due date")
        elif info.days_remaining <= due_soon_days:
            time_state = "due_soon"
            reasons.append(f"due in {info.days_remaining} days")
    if use_hours:
        info.hours_remaining = round(float(inst.interval_hours) - usage_hours_since, 2)
        if info.hours_remaining <= 0:
            hours_state = "overdue"
            reasons.append(f"{-info.hours_remaining:g} h over the {inst.interval_hours:g} h usage limit")
        elif info.hours_remaining <= float(inst.interval_hours) * usage_fraction:
            hours_state = "due_soon"
            reasons.append(f"{info.hours_remaining:g} h of usage left")

    if info.status == "ok":
        if "overdue" in (time_state, hours_state):
            info.status = "overdue"
        elif "due_soon" in (time_state, hours_state):
            info.status = "due_soon"
        info.reason = "; ".join(reasons).capitalize()
    return info


def load_due(db: Session, instruments: list[Instrument]) -> dict[int, DueInfo]:
    """Evaluate many instruments with two queries (latest calibrations, usage sessions)."""
    if not instruments:
        return {}
    ids = [i.id for i in instruments]
    latest: dict[int, Calibration] = {}
    cals = db.execute(
        select(Calibration).where(Calibration.instrument_id.in_(ids)).order_by(Calibration.performed_on.desc(), Calibration.id.desc())
    ).scalars()
    for c in cals:
        latest.setdefault(c.instrument_id, c)

    sessions: dict[int, list[tuple[datetime, float]]] = {}
    if latest:
        floor = datetime.combine(min(c.performed_on for c in latest.values()), datetime.min.time())
        now = utcnow()
        rows = db.execute(
            select(UsageSession.instrument_id, UsageSession.started_at, UsageSession.ended_at, UsageSession.hours)
            .where(UsageSession.instrument_id.in_(ids), UsageSession.started_at >= floor)
        ).all()
        for iid, started, ended, hours in rows:
            h = hours if ended is not None and hours is not None else max(0.0, (now - started).total_seconds() / 3600)
            sessions.setdefault(iid, []).append((started, h))

    today = today_local()
    out = {}
    for inst in instruments:
        cal = latest.get(inst.id)
        used = 0.0
        if cal:
            cutoff = datetime.combine(cal.performed_on, datetime.min.time())
            used = sum(h for st, h in sessions.get(inst.id, []) if st >= cutoff)
        out[inst.id] = evaluate(inst, cal, used, today)
    return out


def scan(db: Session) -> dict:
    """Full scan used by the scheduled Lambda / admin button: group everything needing attention by department."""
    instruments = db.execute(select(Instrument).where(Instrument.status != "retired")).scalars().all()
    infos = load_due(db, instruments)
    by_dept: dict[str, list[dict]] = {}
    counts = {k: 0 for k in ("ok", "due_soon", "overdue", "failed", "uncalibrated", "out_of_service")}
    for inst in instruments:
        info = infos[inst.id]
        counts[info.status] = counts.get(info.status, 0) + 1
        if info.status in ATTENTION:
            by_dept.setdefault(inst.department.code, []).append(
                {"asset_tag": inst.asset_tag, "name": inst.name, "status": info.status, "reason": info.reason,
                 "next_due_on": info.next_due_on.isoformat() if info.next_due_on else None}
            )
    return {"scanned": len(instruments), "counts": counts, "attention": by_dept}


def digest_text(result: dict) -> str:
    lines = [f"Calibration scan - {today_local().isoformat()}", f"Instruments scanned: {result['scanned']}", ""]
    c = result["counts"]
    lines.append(f"OK {c.get('ok', 0)} | Due soon {c.get('due_soon', 0)} | Overdue {c.get('overdue', 0)} | "
                 f"Failed {c.get('failed', 0)} | Uncalibrated {c.get('uncalibrated', 0)}")
    order = {"overdue": 0, "failed": 1, "uncalibrated": 2, "due_soon": 3}
    for dept, items in sorted(result["attention"].items()):
        lines += ["", f"[{dept}]"]
        for it in sorted(items, key=lambda x: order.get(x["status"], 9)):
            lines.append(f"  {it['status'].upper():<12} {it['asset_tag']:<14} {it['name']} - {it['reason']}")
    return "\n".join(lines)
