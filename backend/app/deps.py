import hmac

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User
from .security import decode_token


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    try:
        claims = decode_token(authorization[7:])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired - please sign in again")
    if "uid" not in claims:
        raise HTTPException(401, "Invalid token")
    user = db.execute(select(User).where(User.id == claims["uid"])).scalar_one_or_none()
    if not user or not user.active:
        raise HTTPException(401, "Account disabled")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


def device_key(x_device_key: str = Header(default="")) -> str:
    if not hmac.compare_digest(x_device_key.encode(), get_settings().device_api_key.encode()):
        raise HTTPException(401, "Invalid device key")
    return "device"
