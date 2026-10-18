import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="cad-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["LOCAL_STORAGE_DIR"] = str(_tmp / "files")
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DEVICE_API_KEY"] = "test-device-key"
os.environ["FRONTEND_DIST"] = str(_tmp / "no-frontend")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Department, User  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        ele, mec = Department(code="ELE", name="Electronics"), Department(code="MEC", name="Mechanical")
        db.add_all([ele, mec])
        db.flush()
        pw = hash_password("password123")
        db.add_all([
            User(email="admin@t.io", name="Admin", role="admin", password_hash=pw),
            User(email="head@t.io", name="Head", role="head", password_hash=pw),
            User(email="ele@t.io", name="Ele", role="incharge", department_id=ele.id, password_hash=pw),
            User(email="mec@t.io", name="Mec", role="incharge", department_id=mec.id, password_hash=pw),
        ])
        db.commit()
    with TestClient(app) as c:
        yield c


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}
