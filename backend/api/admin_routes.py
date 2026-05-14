"""
Admin routes — user management (admin role required).

GET    /api/admin/users        — list all users
POST   /api/admin/users        — create user
PATCH  /api/admin/users/{id}   — update active/role/password
DELETE /api/admin/users/{id}   — delete user (cannot delete own account)
"""


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend import database as db
from backend.auth import hash_password, require_admin

router = APIRouter()


class CreateUserBody(BaseModel):
    email: str
    password: str
    role: str = "user"


class UpdateUserBody(BaseModel):
    active: Optional[int] = None   # 1 = active, 0 = deactivated
    role: Optional[str] = None     # "admin" or "user"
    password: Optional[str] = None


def _safe_user(u: dict) -> dict:
    """Strip password_hash from user dict before returning to client."""
    return {k: v for k, v in u.items() if k != "password_hash"}


@router.get("/admin/users")
async def list_users(admin: dict = Depends(require_admin)):
    return {"users": [_safe_user(u) for u in db.list_users()]}


@router.post("/admin/users", status_code=201)
async def create_user(body: CreateUserBody, admin: dict = Depends(require_admin)):
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'.")
    if db.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail=f"Email '{body.email}' is already registered.")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    user_id = db.create_user(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    user = db.get_user_by_id(user_id)
    return {"user": _safe_user(user)}


@router.patch("/admin/users/{user_id}")
async def update_user(user_id: int, body: UpdateUserBody, admin: dict = Depends(require_admin)):
    target = db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    updates = {}
    if body.active is not None:
        # Admin cannot deactivate themselves
        if user_id == admin["id"] and body.active == 0:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
        updates["active"] = body.active

    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'.")
        updates["role"] = body.role

    if body.password is not None:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
        updates["password_hash"] = hash_password(body.password)

    if updates:
        db.update_user(user_id, **updates)

    user = db.get_user_by_id(user_id)
    return {"user": _safe_user(user)}


@router.delete("/admin/users/{user_id}", status_code=200)
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    target = db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    with db._conn() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    return {"deleted": user_id}
