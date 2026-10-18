from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit as audit_svc
from .. import policy
from ..db import get_db
from ..deps import current_user
from ..models import AuditLog, User
from ..schemas import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=dict)
def list_entries(
    limit: int = 50, offset: int = 0, entity: str = "", action: str = "", q: str = "",
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    stmt = select(AuditLog)
    f = policy.scope(user, AuditLog.department_id)
    if f is not None:
        stmt = stmt.where(f)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if action:
        stmt = stmt.where(AuditLog.action.like(action + "%"))
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(AuditLog.detail.ilike(like) | AuditLog.actor.ilike(like) | AuditLog.entity_id.ilike(like))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(AuditLog.id.desc()).offset(max(0, offset)).limit(min(limit, 200))).scalars().all()
    return {"total": total, "items": [AuditOut.model_validate(r).model_dump(mode="json") for r in rows]}


@router.get("/verify")
def verify(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not policy.sees_all(user):
        raise HTTPException(403, "Chain verification covers all departments; ask an administrator or department head")
    return audit_svc.verify_chain(db)
