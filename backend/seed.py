"""Load realistic demo data for local testing.

    python seed.py            # seed an empty database
    python seed.py --reset    # wipe everything (tables + local certificate files) and re-seed

All demo accounts share the password below. Never run this against a production database.
"""
import hashlib
import random
import shutil
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import audit
from app.config import get_settings
from app.db import Base, SessionLocal, engine, init_db, utcnow
from app.models import Calibration, Department, Instrument, LabAccess, UsageSession, User
from app.security import hash_password
from app.services.due import today_local
from app.storage import get_storage

PASSWORD = "Vit@2026"
rng = random.Random(2026)

DEPARTMENTS = [
    ("ELE", "Electronics & Communication"),
    ("MEC", "Mechanical Engineering"),
    ("CHE", "Chemistry"),
    ("PHY", "Physics"),
    ("BIO", "Biotechnology"),
]

# (name, category, make, model, mode, interval_days, scenario)
# scenario: ok | soon | over | none | fail | oos | hours_ok | hours_soon | hours_over
INSTRUMENTS = {
    "ELE": [
        ("Digital Storage Oscilloscope", "Electronics", "Keysight", "DSOX1204G", "time", 365, "ok"),
        ("Digital Multimeter", "Electronics", "Fluke", "87V", "time", 365, "ok"),
        ("Function Generator", "Electronics", "Tektronix", "AFG1022", "time", 365, "soon"),
        ("DC Power Supply", "Electronics", "Rigol", "DP832", "time", 365, "ok"),
        ("Spectrum Analyzer", "Electronics", "Rohde & Schwarz", "FPC1000", "time", 180, "over"),
        ("LCR Meter", "Electronics", "Keysight", "E4980A", "time", 365, "ok"),
        ("Logic Analyzer", "Electronics", "Saleae", "Logic Pro 16", "time", 730, "ok"),
        ("Frequency Counter", "Electronics", "Tektronix", "FCA3000", "time", 365, "soon"),
    ],
    "MEC": [
        ("Universal Testing Machine 100 kN", "Mechanical", "Instron", "5985", "both", 365, "hours_soon"),
        ("Digital Vernier Caliper", "Dimensional", "Mitutoyo", "CD-6 ASX", "time", 180, "ok"),
        ("Outside Micrometer 0-25 mm", "Dimensional", "Mitutoyo", "293-240", "time", 365, "ok"),
        ("Bourdon Pressure Gauge 0-10 bar", "Pressure", "WIKA", "213.53", "time", 180, "over"),
        ("Dial Gauge", "Dimensional", "Mitutoyo", "2046S", "time", 365, "ok"),
        ("Torque Wrench 20-200 Nm", "Mechanical", "Norbar", "TTi 200", "time", 365, "fail"),
        ("Rockwell Hardness Tester", "Mechanical", "Wilson", "RB2000", "both", 365, "hours_ok"),
        ("Digital Tachometer", "Electronics", "Testo", "470", "time", 365, "soon"),
    ],
    "CHE": [
        ("UV-Vis Spectrophotometer", "Optical", "Shimadzu", "UV-1800", "both", 365, "hours_ok"),
        ("Benchtop pH Meter", "Electrochemical", "Mettler Toledo", "S220", "time", 90, "soon"),
        ("Analytical Balance 220 g", "Weighing", "Sartorius", "Entris II", "time", 365, "ok"),
        ("Conductivity Meter", "Electrochemical", "Hanna", "HI5522", "time", 180, "ok"),
        ("Karl Fischer Titrator", "Electrochemical", "Metrohm", "915 KF Ti-Touch", "time", 365, "over"),
        ("Polarimeter", "Optical", "Anton Paar", "MCP 100", "time", 365, "ok"),
        ("Abbe Refractometer", "Optical", "Atago", "NAR-1T", "time", 365, "ok"),
        ("Hot Air Oven Thermometer", "Temperature", "Testo", "110", "time", 180, "ok"),
    ],
    "PHY": [
        ("Laser Power Meter", "Optical", "Thorlabs", "PM100D", "time", 365, "ok"),
        ("Gaussmeter", "Magnetic", "Lake Shore", "425", "time", 365, "none"),
        ("Digital Barometer", "Pressure", "Vaisala", "PTB330", "time", 365, "ok"),
        ("Optical Spectrometer", "Optical", "Ocean Optics", "HR4000", "both", 365, "hours_ok"),
        ("Digital Stopwatch Set", "Time", "Casio", "HS-80TW", "time", 730, "ok"),
        ("Precision Thermometer", "Temperature", "Fluke", "1524", "time", 365, "soon"),
        ("Four-Probe Resistivity Setup", "Electronics", "Scientific Equipment", "SES-FP", "time", 365, "ok"),
        ("Lux Meter", "Optical", "Extech", "LT300", "time", 365, "over"),
    ],
    "BIO": [
        ("Analytical Balance 0.1 mg", "Weighing", "Mettler Toledo", "ML204T", "time", 365, "ok"),
        ("Micropipette P1000", "Volumetric", "Eppendorf", "Research plus", "time", 180, "soon"),
        ("Autoclave Pressure Gauge", "Pressure", "WIKA", "233.50", "time", 365, "ok"),
        ("Refrigerated Centrifuge", "Mechanical", "Eppendorf", "5810R", "both", 365, "hours_over"),
        ("PCR Thermal Cycler", "Temperature", "Bio-Rad", "T100", "both", 365, "hours_ok"),
        ("Benchtop pH Meter", "Electrochemical", "Mettler Toledo", "S220", "time", 90, "ok"),
        ("Microplate Spectrophotometer", "Optical", "Thermo Fisher", "Multiskan GO", "time", 365, "oos"),
        ("Incubator Thermometer", "Temperature", "Testo", "110", "time", 180, "ok"),
    ],
}


def tiny_pdf(title: str, lines: list[str]) -> bytes:
    """Hand-built single-page PDF so demo certificates open in any viewer."""
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = "BT /F1 18 Tf 60 780 Td (" + esc(title) + ") Tj /F1 11 Tf "
    for ln in lines:
        content += "0 -22 Td (" + esc(ln) + ") Tj "
    content += "ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def main(reset: bool) -> None:
    s = get_settings()
    if reset:
        Base.metadata.drop_all(engine)
        if s.storage_backend == "local" and s.local_storage_dir.exists():
            shutil.rmtree(s.local_storage_dir)
    init_db()
    db = SessionLocal()
    if db.execute(select(User)).first():
        sys.exit("Database already has data - run with --reset to wipe and re-seed.")

    now, today = utcnow(), today_local()
    store = get_storage()
    pw = hash_password(PASSWORD)
    audit_events: list[tuple] = []  # (ts, actor, action, entity, entity_id, dept_id, detail)

    depts = {}
    for code, name in DEPARTMENTS:
        d = Department(code=code, name=name)
        db.add(d)
        depts[code] = d
    db.flush()

    # Fictional demo people
    db.add(User(email="admin@vit.ac.in", name="Meera Nair", role="admin", password_hash=pw))
    db.add(User(email="head@vit.ac.in", name="Prof. Arvind Kumar", role="head", password_hash=pw))
    incharge = {
        "ELE": ("electronics@vit.ac.in", "Suresh Babu"),
        "MEC": ("mechanical@vit.ac.in", "Lakshmi Iyer"),
        "CHE": ("chemistry@vit.ac.in", "Farhan Ali"),
        "PHY": ("physics@vit.ac.in", "Deepa Reddy"),
        "BIO": ("biotech@vit.ac.in", "Nikhil Joshi"),
    }
    for code, (email, name) in incharge.items():
        db.add(User(email=email, name=name, role="incharge", department_id=depts[code].id, password_hash=pw))
    db.flush()

    people = [f"{y}B{b}{rng.randint(1000, 9999)}" for y in (22, 23, 24) for b in ("EC", "ME", "CH", "PH", "BT") for _ in range(2)]
    people += ["Prof. Rao", "Dr. Iyer", "Tech. Murugan", "Tech. Selvi"]
    open_sessions = 0

    for code, items in INSTRUMENTS.items():
        dept = depts[code]
        lab_incharge = incharge[code][0]
        for n, (name, cat, make, model, mode, days, scenario) in enumerate(items, 1):
            tag = f"VIT-{code}-{n:03d}"
            comm = today - timedelta(days=rng.randint(400, 1800))
            inst = Instrument(
                asset_tag=tag, name=name, category=cat, make=make, model=model, serial_no=f"{make[:3].upper()}{rng.randint(100000, 999999)}",
                location=f"{dept.name.split()[0]} Lab {rng.choice(['101', '102', '204', '210', '305'])}", department_id=dept.id,
                calibration_mode=mode, interval_days=days if mode in ("time", "both") else None,
                interval_hours=500.0 if mode in ("usage", "both") else None, commissioned_on=comm,
                status="out_of_service" if scenario == "oos" else "active",
            )
            db.add(inst)
            db.flush()
            audit_events.append((datetime.combine(comm, datetime.min.time()) + timedelta(hours=6), lab_incharge, "instrument.create", "instrument", inst.id, dept.id, {"asset_tag": tag, "name": name}))

            # How long ago was the most recent calibration?
            if scenario in ("ok", "hours_ok", "hours_soon", "hours_over", "oos"):
                ago = rng.randint(int(days * 0.15), int(days * 0.6))
            elif scenario == "soon":
                ago = days - rng.randint(4, 24)
            elif scenario == "over":
                ago = days + rng.randint(12, 90)
            elif scenario == "fail":
                ago = rng.randint(10, 40)
            else:
                ago = None
            if scenario.startswith("hours"):
                ago = min(ago, 40)  # keep usage window inside the 45 days of seeded sessions

            if ago is not None:
                for k, cal_ago in enumerate((ago, ago + days, ago + 2 * days)):
                    if k and rng.random() < 0.35:
                        break
                    on = today - timedelta(days=cal_ago)
                    if on < comm:
                        break
                    result = "fail" if (scenario == "fail" and k == 0) else rng.choice(["pass", "pass", "pass", "adjusted"])
                    cert_no = f"CERT/{code}/{on.year}/{rng.randint(1000, 9999)}"
                    lab = rng.choice(["Tricolor Calibration Labs", "TUV SUD NABL Lab", "Internal metrology cell", "Elico NABL Services"])
                    pdf = tiny_pdf(f"Calibration Certificate {cert_no}", [f"Instrument: {name} ({tag})", f"Make / model: {make} {model}", f"Calibrated on: {on.isoformat()}", f"Performed by: {lab}", f"Result: {result.upper()}", "Demo certificate - generated by seed.py"])
                    key = f"certificates/{code}/{tag}/{hashlib.sha1(cert_no.encode()).hexdigest()[:16]}.pdf"
                    store.put(key, pdf, "application/pdf")
                    db.add(Calibration(
                        instrument_id=inst.id, performed_on=on, performed_by=lab, certificate_no=cert_no, result=result,
                        notes="Out of tolerance - re-adjustment required." if result == "fail" else "", certificate_key=key,
                        certificate_filename=f"{cert_no.replace('/', '_')}.pdf", certificate_sha256=hashlib.sha256(pdf).hexdigest(),
                        created_by=lab_incharge, created_at=datetime.combine(on, datetime.min.time()) + timedelta(hours=11),
                    ))
                    audit_events.append((datetime.combine(on, datetime.min.time()) + timedelta(hours=11), lab_incharge, "calibration.record", "calibration", f"{tag}", dept.id, {"asset_tag": tag, "performed_on": on, "result": result}))
            db.flush()

            # 45 days of usage sessions
            if scenario not in ("oos",):
                busy = {"Mechanical": 0.7, "Optical": 0.6, "Electronics": 0.9}.get(cat, 0.5)
                for d_ago in range(45, 0, -1):
                    if rng.random() > busy * 0.75:
                        continue
                    start = now - timedelta(days=d_ago, hours=rng.randint(0, 6))
                    start = start.replace(hour=rng.randint(3, 9), minute=rng.choice([0, 15, 30, 45]), second=0, microsecond=0)  # 09:00-15:00 IST in UTC
                    hrs = round(rng.choice([0.5, 1, 1.5, 2, 2.5, 3, 4]) * (1.6 if mode != "time" else 1), 2)
                    db.add(UsageSession(instrument_id=inst.id, user_ref=rng.choice(people), purpose=rng.choice(["Lab experiment", "Project work", "Research", "Practical exam", "Faculty demo"]), started_at=start, ended_at=start + timedelta(hours=hrs), hours=hrs, source=rng.choice(["manual", "device", "device"])))
            db.flush()

            if mode in ("usage", "both") and scenario.startswith("hours"):
                last = db.execute(select(Calibration).where(Calibration.instrument_id == inst.id).order_by(Calibration.performed_on.desc())).scalars().first()
                cutoff = datetime.combine(last.performed_on, datetime.min.time())
                used = sum(u.hours for u in db.execute(select(UsageSession).where(UsageSession.instrument_id == inst.id, UsageSession.started_at >= cutoff)).scalars())
                frac = {"hours_ok": 0.45, "hours_soon": 0.93, "hours_over": 1.15}[scenario]
                inst.interval_hours = max(10.0, round(used / frac, 0))

    # A couple of instruments running right now
    for tag, who in (("VIT-ELE-001", "23BEC1187"), ("VIT-CHE-001", "Tech. Selvi")):
        inst = db.execute(select(Instrument).where(Instrument.asset_tag == tag)).scalar_one()
        db.add(UsageSession(instrument_id=inst.id, user_ref=who, purpose="Lab experiment", started_at=now - timedelta(minutes=rng.randint(20, 90)), source="device"))

    # Lab access swipes: 14 days of in/out pairs, and a few people still inside today
    for code, dept in depts.items():
        for d_ago in range(14, 0, -1):
            day = now - timedelta(days=d_ago)
            if day.weekday() == 6:
                continue
            for p in rng.sample(people, rng.randint(5, 10)):
                t_in = day.replace(hour=rng.randint(3, 8), minute=rng.randint(0, 59), second=0, microsecond=0)
                card = f"04:{rng.randint(16, 255):02X}:{rng.randint(16, 255):02X}:{rng.randint(16, 255):02X}"
                db.add(LabAccess(department_id=dept.id, person_ref=p, card_uid=card, direction="in", method="rfid", at=t_in))
                db.add(LabAccess(department_id=dept.id, person_ref=p, card_uid=card, direction="out", method="rfid", at=t_in + timedelta(minutes=rng.randint(40, 200))))
        for p in rng.sample(people, rng.randint(2, 4)):
            db.add(LabAccess(department_id=dept.id, person_ref=p, card_uid="04:A1:B2:C3", direction="in", method="rfid", at=now - timedelta(minutes=rng.randint(10, 150))))

    # Audit chain, written in chronological order so the trail reads naturally
    for ts, actor, action, entity, eid, dept_id, detail in sorted(audit_events, key=lambda e: e[0]):
        audit.record(db, actor, action, entity, eid, dept_id, detail, ts=ts)
    audit.record(db, "admin@vit.ac.in", "scan.run", "system", "", None, {"note": "initial seed"})
    db.commit()

    n_inst = db.execute(select(Instrument)).scalars().all()
    print(f"Seeded {len(depts)} departments, {len(n_inst)} instruments, 7 users (password: {PASSWORD}).")
    print("Logins: admin@vit.ac.in | head@vit.ac.in | electronics@vit.ac.in | mechanical@vit.ac.in | chemistry@vit.ac.in | physics@vit.ac.in | biotech@vit.ac.in")


if __name__ == "__main__":
    main("--reset" in sys.argv)
