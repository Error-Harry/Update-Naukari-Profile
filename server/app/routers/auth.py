"""Authentication endpoints (register / login)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.db import get_db
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=security.hash_password(payload.password),
        subscription="free",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# Pre-computed bcrypt hash of an arbitrary string. Used only to burn roughly
# the same CPU time when a login attempt is made for a non-existent email, so
# the endpoint doesn't leak user-existence via response timing.
_DUMMY_HASH = security.hash_password("pst-placeholder-for-timing-defense")


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    # Always run bcrypt so the unknown-email branch takes the same wall-clock
    # time as a real login attempt — attackers can't probe which emails exist.
    pw_hash = user.password_hash if user else _DUMMY_HASH
    valid = security.verify_password(payload.password, pw_hash)
    if not user or not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = security.create_access_token(user.id, extra={"email": user.email})
    return TokenOut(access_token=token)
