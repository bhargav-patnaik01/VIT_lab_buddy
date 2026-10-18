from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import LoginIn, LoginOut, UserOut
from ..security import hash_password, make_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the email is unknown so response time doesn't reveal which emails exist.
_DUMMY = hash_password("not-a-real-password")


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, name=u.name, role=u.role, department_id=u.department_id,
        department_code=u.department.code if u.department else None, active=u.active,
    )


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower())).scalar_one_or_none()
    ok = verify_password(body.password, user.password_hash if user else _DUMMY)
    if not user or not ok or not user.active:
        raise HTTPException(401, "Incorrect email or password")
    audit.record(db, user.email, "login", "user", user.id, user.department_id)
    db.commit()
    return LoginOut(token=make_token({"uid": user.id, "role": user.role}), user=user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user_out(user)
