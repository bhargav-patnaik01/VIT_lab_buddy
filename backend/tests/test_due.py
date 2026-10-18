from datetime import date, timedelta
from types import SimpleNamespace

from app.services.due import evaluate

TODAY = date(2026, 10, 18)


def inst(mode="time", days=365, hours=None, status="active"):
    return SimpleNamespace(calibration_mode=mode, interval_days=days, interval_hours=hours, status=status)


def cal(days_ago, result="pass"):
    return SimpleNamespace(performed_on=TODAY - timedelta(days=days_ago), result=result)


def test_ok_far_from_due():
    r = evaluate(inst(), cal(30), 0, TODAY)
    assert r.status == "ok" and r.days_remaining == 335 and r.next_due_on == TODAY + timedelta(days=335)


def test_due_soon_inside_window():
    assert evaluate(inst(), cal(350), 0, TODAY).status == "due_soon"


def test_due_on_the_day_is_not_overdue():
    r = evaluate(inst(), cal(365), 0, TODAY)
    assert r.days_remaining == 0 and r.status == "due_soon"


def test_overdue_after_due_date():
    r = evaluate(inst(), cal(400), 0, TODAY)
    assert r.status == "overdue" and "35 days" in r.reason


def test_uncalibrated_without_record():
    assert evaluate(inst(), None, 0, TODAY).status == "uncalibrated"


def test_failed_last_calibration_overrides_ok():
    assert evaluate(inst(), cal(5, "fail"), 0, TODAY).status == "failed"


def test_usage_mode_overdue_by_hours():
    r = evaluate(inst("usage", None, 500), cal(10), 510, TODAY)
    assert r.status == "overdue" and r.hours_remaining == -10 and r.next_due_on is None


def test_usage_mode_due_soon_within_ten_percent():
    assert evaluate(inst("usage", None, 500), cal(10), 460, TODAY).status == "due_soon"
    assert evaluate(inst("usage", None, 500), cal(10), 300, TODAY).status == "ok"


def test_both_mode_whichever_comes_first():
    # time is fine, hours exhausted -> overdue
    assert evaluate(inst("both", 365, 100), cal(30), 120, TODAY).status == "overdue"
    # hours fine, time lapsed -> overdue
    assert evaluate(inst("both", 365, 100), cal(400), 5, TODAY).status == "overdue"


def test_retired_and_out_of_service():
    assert evaluate(inst(status="retired"), cal(999), 0, TODAY).status == "retired"
    assert evaluate(inst(status="out_of_service"), cal(999), 0, TODAY).status == "out_of_service"
