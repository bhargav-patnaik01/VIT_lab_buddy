import io
from datetime import date

from sqlalchemy import text

from app.db import SessionLocal, engine

from .conftest import login

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def new_instrument(client, h, dept_id, tag="T-001", **kw):
    body = {"asset_tag": tag, "name": "Test Scope", "department_id": dept_id, "calibration_mode": "time", "interval_days": 365, **kw}
    return client.post("/api/instruments", json=body, headers=h)


def dept_ids(client, h):
    return {d["code"]: d["id"] for d in client.get("/api/departments", headers=h).json()}


def test_requires_auth(client):
    assert client.get("/api/instruments").status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@t.io", "password": "wrong"}).status_code == 401


def test_incharge_cannot_see_or_touch_other_department(client):
    admin, ele, mec = login(client, "admin@t.io"), login(client, "ele@t.io"), login(client, "mec@t.io")
    ids = dept_ids(client, admin)
    assert new_instrument(client, ele, ids["ELE"]).status_code == 201
    inst_id = client.get("/api/instruments", headers=ele).json()[0]["id"]

    # Mechanical in-charge: list is empty, direct access is 404 (indistinguishable from missing), writes are 404
    assert client.get("/api/instruments", headers=mec).json() == []
    assert client.get(f"/api/instruments/{inst_id}", headers=mec).status_code == 404
    assert client.put(f"/api/instruments/{inst_id}", json={"name": "hijack"}, headers=mec).status_code == 404
    assert client.get(f"/api/instruments/{inst_id}/calibrations", headers=mec).status_code == 404
    assert client.post(f"/api/instruments/{inst_id}/usage/start", json={"user_ref": "x"}, headers=mec).status_code == 404
    # and cannot create into another department
    assert new_instrument(client, mec, ids["ELE"], tag="T-002").status_code == 404
    # departments list is scoped too
    assert [d["code"] for d in client.get("/api/departments", headers=mec).json()] == ["MEC"]


def test_head_reads_everything_but_cannot_write(client):
    admin, ele, head = login(client, "admin@t.io"), login(client, "ele@t.io"), login(client, "head@t.io")
    ids = dept_ids(client, admin)
    new_instrument(client, ele, ids["ELE"])
    items = client.get("/api/instruments", headers=head).json()
    assert len(items) == 1
    r = client.put(f"/api/instruments/{items[0]['id']}", json={"name": "x"}, headers=head)
    assert r.status_code == 403
    assert new_instrument(client, head, ids["ELE"], tag="T-9").status_code == 403
    assert client.get("/api/users", headers=head).status_code == 403


def test_calibration_with_certificate_changes_status_and_is_audited(client):
    admin, ele = login(client, "admin@t.io"), login(client, "ele@t.io")
    ids = dept_ids(client, admin)
    new_instrument(client, ele, ids["ELE"])
    inst = client.get("/api/instruments", headers=ele).json()[0]
    assert inst["due"]["status"] == "uncalibrated"

    r = client.post(
        f"/api/instruments/{inst['id']}/calibrations", headers=ele,
        data={"performed_on": date.today().isoformat(), "performed_by": "NABL Lab", "certificate_no": "C-1", "result": "pass"},
        files={"certificate": ("cert.pdf", io.BytesIO(PDF), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    cal = r.json()
    assert cal["has_certificate"] and len(cal["certificate_sha256"]) == 64
    assert client.get(f"/api/instruments/{inst['id']}", headers=ele).json()["due"]["status"] == "ok"

    url = client.get(f"/api/calibrations/{cal['id']}/certificate-url", headers=ele).json()["url"]
    f = client.get(url)
    assert f.status_code == 200 and f.content == PDF
    # another department cannot even resolve the link
    assert client.get(f"/api/calibrations/{cal['id']}/certificate-url", headers=login(client, "mec@t.io")).status_code == 404


def test_certificate_rejects_wrong_type_and_spoofed_content(client):
    admin, ele = login(client, "admin@t.io"), login(client, "ele@t.io")
    new_instrument(client, ele, dept_ids(client, admin)["ELE"])
    iid = client.get("/api/instruments", headers=ele).json()[0]["id"]
    base = {"performed_on": date.today().isoformat(), "result": "pass"}
    r = client.post(f"/api/instruments/{iid}/calibrations", headers=ele, data=base, files={"certificate": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    assert r.status_code == 422
    r = client.post(f"/api/instruments/{iid}/calibrations", headers=ele, data=base, files={"certificate": ("x.pdf", io.BytesIO(b"<html>"), "application/pdf")})
    assert r.status_code == 422


def test_usage_hours_trigger_usage_based_calibration(client):
    admin, ele = login(client, "admin@t.io"), login(client, "ele@t.io")
    new_instrument(client, ele, dept_ids(client, admin)["ELE"], calibration_mode="usage", interval_days=None, interval_hours=10)
    iid = client.get("/api/instruments", headers=ele).json()[0]["id"]
    client.post(f"/api/instruments/{iid}/calibrations", headers=ele, data={"performed_on": date.today().isoformat(), "result": "pass"})
    assert client.get(f"/api/instruments/{iid}", headers=ele).json()["due"]["status"] == "ok"

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    r = client.post(f"/api/instruments/{iid}/usage", json={"user_ref": "student", "started_at": now, "hours": 11}, headers=ele)
    assert r.status_code == 201, r.text
    # started_at is 'now' (>= today's midnight), so the 11 h count against the 10 h limit
    assert client.get(f"/api/instruments/{iid}", headers=ele).json()["due"]["status"] == "overdue"


def test_usage_start_stop_and_double_start_conflict(client):
    admin, ele = login(client, "admin@t.io"), login(client, "ele@t.io")
    new_instrument(client, ele, dept_ids(client, admin)["ELE"])
    iid = client.get("/api/instruments", headers=ele).json()[0]["id"]
    assert client.post(f"/api/instruments/{iid}/usage/start", json={"user_ref": "a"}, headers=ele).status_code == 201
    assert client.post(f"/api/instruments/{iid}/usage/start", json={"user_ref": "b"}, headers=ele).status_code == 409
    assert client.get(f"/api/instruments/{iid}", headers=ele).json()["in_use"] is True
    assert client.post(f"/api/instruments/{iid}/usage/stop", headers=ele).status_code == 200
    assert client.post(f"/api/instruments/{iid}/usage/stop", headers=ele).status_code == 409


def test_audit_chain_verifies_and_detects_tampering(client):
    admin, ele = login(client, "admin@t.io"), login(client, "ele@t.io")
    new_instrument(client, ele, dept_ids(client, admin)["ELE"])
    assert client.get("/api/audit/verify", headers=admin).json()["ok"] is True

    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_log SET detail = 'forged' WHERE id = (SELECT MIN(id) FROM audit_log)"))
    v = client.get("/api/audit/verify", headers=admin).json()
    assert v["ok"] is False and v["broken_at"] is not None
    # in-charges cannot run the global verification
    assert client.get("/api/audit/verify", headers=ele).status_code == 403


def test_audit_log_is_department_scoped(client):
    admin, ele, mec = login(client, "admin@t.io"), login(client, "ele@t.io"), login(client, "mec@t.io")
    new_instrument(client, ele, dept_ids(client, admin)["ELE"])
    ele_rows = client.get("/api/audit?entity=instrument", headers=ele).json()["items"]
    mec_rows = client.get("/api/audit?entity=instrument", headers=mec).json()["items"]
    assert len(ele_rows) == 1 and mec_rows == []


def test_device_ingest_requires_key_and_feeds_lab_occupancy(client):
    admin, ele = login(client, "admin@t.io"), login(client, "ele@t.io")
    new_instrument(client, ele, dept_ids(client, admin)["ELE"])
    swipe = {"dept_code": "ELE", "person_ref": "23BEC1001", "direction": "in", "card_uid": "04:AA"}
    assert client.post("/api/ingest/access", json=swipe).status_code == 401
    assert client.post("/api/ingest/access", json=swipe, headers={"X-Device-Key": "test-device-key"}).status_code == 201
    labs = client.get("/api/access/summary", headers=ele).json()
    assert labs[0]["inside"] == ["23BEC1001"] and labs[0]["entries_today"] == 1
    client.post("/api/ingest/access", json={**swipe, "direction": "out"}, headers={"X-Device-Key": "test-device-key"})
    assert client.get("/api/access/summary", headers=ele).json()[0]["inside"] == []


def test_dashboard_scoping_and_csv_export(client):
    admin, ele, head = login(client, "admin@t.io"), login(client, "ele@t.io"), login(client, "head@t.io")
    ids = dept_ids(client, admin)
    new_instrument(client, ele, ids["ELE"], tag="E-1")
    new_instrument(client, admin, ids["MEC"], tag="M-1")
    assert client.get("/api/dashboard", headers=ele).json()["total"] == 1
    assert client.get("/api/dashboard", headers=head).json()["total"] == 2
    csv = client.get("/api/reports/instruments.csv", headers=ele).text
    assert "E-1" in csv and "M-1" not in csv


def test_csv_formula_injection_is_neutralised(client):
    admin = login(client, "admin@t.io")
    new_instrument(client, admin, dept_ids(client, admin)["ELE"], name="=HYPERLINK(\"http://evil\")")
    assert "'=HYPERLINK" in client.get("/api/reports/instruments.csv", headers=admin).text


def test_admin_user_management_rules(client):
    admin = login(client, "admin@t.io")
    ids = dept_ids(client, admin)
    r = client.post("/api/users", json={"email": "n@t.io", "name": "New", "role": "incharge", "password": "password123"}, headers=admin)
    assert r.status_code == 422  # in-charge needs a department
    r = client.post("/api/users", json={"email": "n@t.io", "name": "New", "role": "incharge", "department_id": ids["MEC"], "password": "password123"}, headers=admin)
    assert r.status_code == 201
    assert client.post("/api/users", json={"email": "N@t.io", "name": "Dup", "role": "head", "password": "password123"}, headers=admin).status_code == 409
    me = client.get("/api/auth/me", headers=admin).json()
    assert client.put(f"/api/users/{me['id']}", json={"active": False}, headers=admin).status_code == 422
    # disabled account can no longer use its token
    uid = r.json()["id"]
    h = login(client, "n@t.io")
    client.put(f"/api/users/{uid}", json={"active": False}, headers=admin)
    assert client.get("/api/auth/me", headers=h).status_code == 401
