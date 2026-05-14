"""
JWT authentication utilities for LinkedIn Auto-Poster.

- Passwords hashed with bcrypt (passlib)
- Tokens signed with HS256 (python-jose)
- JWT secret stored in SQLite settings table (auto-generated on first run)
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 8

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _get_jwt_secret() -> str:
    """Read JWT secret from DB settings (auto-generated on init_db)."""
    try:
        from backend.database import get_setting
        secret = get_setting("jwt_secret") or ""
        if secret:
            return secret
    except Exception:
        pass
    # Fallback to env var — fail if neither DB nor env var is set
    env_secret = os.getenv("JWT_SECRET")
    if not env_secret:
        raise RuntimeError(
            "JWT_SECRET not available. Ensure the database is initialized or set the JWT_SECRET env var."
        )
    return env_secret


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_hours: int = _TOKEN_EXPIRE_HOURS) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=expires_hours)
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject.")
    from backend.database import get_user_by_id
    user = get_user_by_id(int(user_id))
    if not user or not user.get("active"):
        raise HTTPException(status_code=401, detail="User not found or deactivated.")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
