"""Seed (or update) the bootstrap admin user.

Creates an admin account with a paid subscription so you can log in and
manage the platform. Safe to re-run — if the user already exists it is
promoted to admin and its subscription is normalised to `paid`; the
password is only rewritten when `--reset-password` is passed.

Defaults:
    email:        updateprofileservice@gmail.com
    password:     Admin@123
    name:         Administrator
    role:         admin
    subscription: paid (subscribed_at = now)

Usage (from the `server/` directory):

    python -m scripts.seed_admin
    python -m scripts.seed_admin --email you@example.com --password 'S3cret!'
    python -m scripts.seed_admin --reset-password
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

# Allow running as `python server/scripts/seed_admin.py` too.
_HERE = os.path.abspath(os.path.dirname(__file__))
_SERVER_DIR = os.path.abspath(os.path.join(_HERE, ".."))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from sqlalchemy import select  # noqa: E402

from app import security  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402


DEFAULT_EMAIL = "updateprofileservice@gmail.com"
DEFAULT_PASSWORD = "Admin@123"
DEFAULT_NAME = "Administrator"


async def _seed(email: str, password: str, name: str, reset_password: bool) -> None:
    # Make sure tables exist even on a fresh DB.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

        if existing is None:
            user = User(
                email=email,
                name=name,
                password_hash=security.hash_password(password),
                role="admin",
                subscription="paid",
                subscribed_at=datetime.now(timezone.utc),
            )
            db.add(user)
            await db.commit()
            print(f"[seed_admin] Created admin user <{email}>")
            print(f"[seed_admin]   password: {password}")
            return

        changed: list[str] = []
        if existing.role != "admin":
            existing.role = "admin"
            changed.append("role=admin")
        if existing.subscription != "paid":
            existing.subscription = "paid"
            existing.subscribed_at = datetime.now(timezone.utc)
            changed.append("subscription=paid")
        elif existing.subscribed_at is None:
            existing.subscribed_at = datetime.now(timezone.utc)
            changed.append("subscribed_at")
        if reset_password:
            existing.password_hash = security.hash_password(password)
            changed.append("password")

        if not changed:
            print(f"[seed_admin] <{email}> already admin + paid — nothing to do")
            return

        await db.commit()
        print(f"[seed_admin] Updated <{email}>: {', '.join(changed)}")
        if reset_password:
            print(f"[seed_admin]   password: {password}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed the bootstrap admin user.")
    p.add_argument("--email", default=DEFAULT_EMAIL, help=f"Admin email (default: {DEFAULT_EMAIL})")
    p.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="Password to set when creating the user (or when --reset-password is passed).",
    )
    p.add_argument("--name", default=DEFAULT_NAME, help=f"Display name (default: {DEFAULT_NAME})")
    p.add_argument(
        "--reset-password",
        action="store_true",
        help="Overwrite the password for an existing user.",
    )
    return p.parse_args()


async def seed_admin(
    email: str,
    password: str,
    name: str,
    reset_password: bool,
) -> None:
    email = email.strip().lower()
    try:
        await _seed(email, password, name, reset_password)
    finally:
        await engine.dispose()


def main() -> None:
    args = _parse_args()
    asyncio.run(
        seed_admin(
            email=args.email,
            password=args.password,
            name=args.name,
            reset_password=args.reset_password,
        )
    )


if __name__ == "__main__":
    main()
