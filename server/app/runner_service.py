"""Executes a single user's Naukri update using the reusable runner + DB state."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.emailer import send_email
from app.models import NaukriProfile, RunLog, User
from app.security import decrypt_secret
from naukari_bot.runner import RunConfig, run_naukri_update

log = logging.getLogger(__name__)

# Serialize browser runs — only one Playwright session at a time on this host.
_BROWSER_SEMAPHORE = asyncio.Semaphore(1)


async def run_for_user(user_id: UUID) -> None:
    """Load the user + profile, run the update, persist a RunLog, email the user."""
    async with _BROWSER_SEMAPHORE:
        await _run_for_user_impl(user_id)


async def _run_for_user_impl(user_id: UUID) -> None:
    async with SessionLocal() as db:
        result = await db.execute(
            select(User, NaukriProfile)
            .join(NaukriProfile, NaukriProfile.user_id == User.id)
            .where(User.id == user_id)
        )
        row = result.first()
        if not row:
            log.warning("No profile for user_id=%s — skipping scheduled run", user_id)
            return
        user, profile = row

        problems = _validate_profile(profile)
        if problems:
            log.warning("Skipping run for %s: %s", user.email, problems)
            await _record_failure(db, user, profile, f"Profile incomplete: {problems}")
            return

        naukri_password = decrypt_secret(profile.naukri_password_enc)
        resume_bytes = profile.resume_bytes
        resume_name = profile.resume_filename or "resume.pdf"

    settings = get_settings()

    user_data_dir = os.path.abspath(
        os.path.join("var", "pw-profiles", str(user_id))
    )
    os.makedirs(user_data_dir, exist_ok=True)

    cfg = RunConfig(
        naukri_email=profile.naukri_email,
        naukri_password=naukri_password,
        resume_bytes=resume_bytes,
        resume_filename=resume_name,
        user_data_dir=user_data_dir,
        headed=settings.playwright_headed,
        max_retries=2,
    )

    log.info("Starting run for user=%s", user.email)
    started_at = datetime.utcnow()
    try:
        result = await run_naukri_update(cfg)
    except Exception as e:  # noqa: BLE001
        log.exception("Unhandled error in runner")
        result = None
        error = str(e)
    else:
        error = result.error if not result.success else None

    async with SessionLocal() as db:
        refreshed = await db.get(NaukriProfile, profile.id)
        if refreshed:
            refreshed.last_run_at = datetime.utcnow()
            refreshed.last_status = "success" if (result and result.success) else "failed"
            refreshed.last_error = None if (result and result.success) else (error or "unknown")
        log_row = RunLog(
            user_id=user.id,
            started_at=started_at,
            finished_at=datetime.utcnow(),
            status="success" if (result and result.success) else "failed",
            attempts=result.attempts if result else 0,
            error=None if (result and result.success) else (error or "unknown"),
        )
        db.add(log_row)
        await db.commit()

    today = datetime.now().strftime("%d-%b-%Y")
    if result and result.success:
        send_email(
            to_email=user.email,
            subject=f"Resume & Profile Updated - {today}",
            body=(
                f"Hi {user.name},\n\n"
                f"Your Naukri profile was updated successfully on {today}.\n\n"
                f"— Naukri Auto Update"
            ),
            attachment_bytes=resume_bytes,
            attachment_name=resume_name,
        )
    else:
        send_email(
            to_email=user.email,
            subject=f"Naukri Update Failed - {today}",
            body=(
                f"Hi {user.name},\n\n"
                f"We couldn't update your Naukri profile today.\n\n"
                f"Reason: {error}\n\n"
                f"Please verify your Naukri credentials and resume on the dashboard.\n\n"
                f"— Naukri Auto Update"
            ),
        )


def _validate_profile(profile: NaukriProfile) -> str | None:
    missing = []
    if not profile.naukri_email:
        missing.append("naukri_email")
    if not profile.naukri_password_enc:
        missing.append("naukri_password")
    if not profile.resume_bytes:
        missing.append("resume")
    if missing:
        return ", ".join(missing)
    return None


async def _record_failure(db, user, profile, reason: str) -> None:
    profile.last_run_at = datetime.utcnow()
    profile.last_status = "skipped"
    profile.last_error = reason
    db.add(
        RunLog(
            user_id=user.id,
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            status="skipped",
            attempts=0,
            error=reason,
        )
    )
    await db.commit()
