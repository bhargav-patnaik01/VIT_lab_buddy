"""Department-scoped access policy.

This is the application-level twin of the IAM policy conditions described in the
project report: every read/write is evaluated against the caller's role and
department. Nothing else in the codebase decides who may see what.

    admin     full read/write on every department, manages users & departments
    head      read-only across every department
    incharge  read/write limited to their own department (lab in-charge)
"""
from fastapi import HTTPException

from .models import User

READ_ALL = {"admin", "head"}
WRITE_ALL = {"admin"}


def can_read(user: User, department_id: int | None) -> bool:
    if user.role in READ_ALL:
        return True
    return user.role == "incharge" and department_id is not None and user.department_id == department_id


def can_write(user: User, department_id: int | None) -> bool:
    if user.role in WRITE_ALL:
        return True
    return user.role == "incharge" and department_id is not None and user.department_id == department_id


def sees_all(user: User) -> bool:
    return user.role in READ_ALL


def scope(user: User, column):
    """SQLAlchemy filter restricting `column` (a department_id) to what `user` may read, or None for no restriction."""
    if sees_all(user):
        return None
    return column == user.department_id


def require_read(user: User, department_id: int | None) -> None:
    # 404 rather than 403 so other departments' records are indistinguishable from non-existent ones.
    if not can_read(user, department_id):
        raise HTTPException(404, "Not found")


def require_write(user: User, department_id: int | None) -> None:
    if not can_read(user, department_id):
        raise HTTPException(404, "Not found")
    if not can_write(user, department_id):
        raise HTTPException(403, "Your role has read-only access to this department")
