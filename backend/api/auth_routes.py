"""
Auth routes: login, logout, current user.

POST /api/auth/login  — email + password → JWT
GET  /api/auth/me     — current user info
"""



from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend import database as db
from backend.auth import (
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter()


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
async def login(body: LoginBody):
    user = db.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.get("active"):
        raise HTTPException(status_code=403, detail="Your account has been deactivated. Contact the admin.")

    token = create_access_token({"sub": str(user["id"]), "email": user["email"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"], "role": user["role"]},
    }


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "role": user["role"]}
