from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, notify
from ..db import get_db
from ..deps import current_user, require_admin
from ..models import Department, User
from ..policy import sees_all
from ..schemas import DepartmentIn, DepartmentOut, UserIn, UserOut, UserUpdate
from ..security import hash_password
from ..services import due
from .auth import user_out

router = APIRouter(tags=["admin"])


# ---- departments
@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Department).order_by(Department.name)
    if not sees_all(user):
        q = q.where(Department.id == user.department_id)
    return db.execute(q).scalars().all()


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = Department(code=body.code.strip().upper(), name=body.name.strip())
    db.add(d)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A department with that code already exists")
    audit.record(db, admin.email, "department.create", "department", d.id, d.id, {"code": d.code, "name": d.name})
    db.commit()
    return d


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
def update_department(dept_id: int, body: DepartmentIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(404, "Not found")
    d.code, d.name = body.code.strip().upper(), body.name.strip()
    try:
        audit.record(db, admin.email, "department.update", "department", d.id, d.id, {"code": d.code, "name": d.name})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A department with that code already exists")
    return d


# ---- users
def _check_role_dept(role: str, department_id: int | None, db: Session):
    if role == "incharge" and not department_id:
        raise HTTPException(422, "A lab in-charge must be assigned to a department")
    if department_id and not db.get(Department, department_id):
        raise HTTPException(422, "Unknown department")


@router.get("/users", response_model=list[UserOut])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.execute(select(User).order_by(User.role, User.name)).scalars()]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _check_role_dept(body.role, body.department_id, db)
    email = body.email.strip().lower()
    if db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none():
        raise HTTPException(409, "A user with that email already exists")
    u = User(
        email=email, name=body.name.strip(), role=body.role, password_hash=hash_password(body.password),
        department_id=body.department_id if body.role == "incharge" else None,
    )
    db.add(u)
    db.flush()
    audit.record(db, admin.email, "user.create", "user", u.id, u.department_id, {"email": u.email, "role": u.role})
    db.commit()
    db.refresh(u)
    return user_out(u)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Not found")
    data = body.model_dump(exclude_unset=True)
    role = data.get("role", u.role)
    dept = data.get("department_id", u.department_id) if role == "incharge" else None
    _check_role_dept(role, dept, db)
    if u.id == admin.id and (role != "admin" or data.get("active") is False):
        raise HTTPException(422, "You cannot demote or disable your own account")
    changed = []
    if "name" in data and data["name"]:
        u.name = data["name"].strip()
        changed.append("name")
    if "active" in data and data["active"] is not None:
        u.active = data["active"]
        changed.append("active")
    if role != u.role or dept != u.department_id:
        u.role, u.department_id = role, dept
        changed += ["role", "department"]
    if data.get("password"):
        u.password_hash = hash_password(data["password"])
        changed.append("password")
    audit.record(db, admin.email, "user.update", "user", u.id, u.department_id, {"email": u.email, "changed": changed})
    db.commit()
    db.refresh(u)
    return user_out(u)


# ---- manual trigger of the same scan the scheduled Lambda runs
@router.post("/admin/scan")
def run_scan(notify_users: bool = False, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = due.scan(db)
    channel = None
    if notify_users:
        channel = notify.publish("Calibration scan digest", due.digest_text(result))
    audit.record(db, admin.email, "scan.run", "system", "", None, {"counts": result["counts"], "notified": channel})
    db.commit()
    return {**result, "notified_via": channel, "digest": due.digest_text(result)}
