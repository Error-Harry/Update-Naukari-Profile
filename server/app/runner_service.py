"""Executes a single user's Naukri update using the reusable runner + DB state."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.config import get_settings
from app.db import SessionLocal
from app.emailer import send_email_async
from app.models import NaukriProfile, RunLog, User
from app.naming import build_resume_filename
from app.security import decrypt_secret, encrypt_secret
from naukari_bot.runner import RunConfig, run_naukri_update

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Timezone-aware UTC. `datetime.utcnow()` is deprecated in 3.12."""
    return datetime.now(timezone.utc)


# How many Playwright browsers may run concurrently on this host. Tune via env
# — 2 is a safe default on a 2 vCPU / 4 GB box with xvfb. Each browser costs
# roughly ~300-500 MB RSS plus CPU during login.
_BROWSER_CONCURRENCY = max(1, int(os.getenv("BROWSER_CONCURRENCY", "2")))
_BROWSER_SEMAPHORE = asyncio.Semaphore(_BROWSER_CONCURRENCY)

# Per-user lock prevents the same user's runs from racing over their own
# `naukri_session_enc` blob, resume upload, or headline edit. Global
# semaphore above caps total parallelism; per-user lock serialises *that*
# user. Creating a lock is cheap; they live for the lifetime of the process.
_USER_LOCKS: dict[UUID, asyncio.Lock] = {}


def _lock_for(user_id: UUID) -> asyncio.Lock:
    # No `await` between get and assign → single-threaded asyncio race-free.
    lock = _USER_LOCKS.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _USER_LOCKS[user_id] = lock
    return lock


# Legacy per-user persistent Playwright profile dirs — we now keep the session
# state in the DB (see NaukriProfile.naukri_session_enc). We lazily wipe any
# lingering dir the first time we run after the upgrade so old hosts stay tidy.
_LEGACY_PW_PROFILE_ROOT = os.path.join("var", "pw-profiles")


# We keep strong refs to background tasks so the asyncio event loop doesn't
# garbage-collect them mid-flight (a known gotcha with `create_task`:
# https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task).
_BG_TASKS: set[asyncio.Task] = set()


def spawn_run_for_user(user_id: UUID) -> asyncio.Task:
    """Fire-and-forget wrapper around `run_for_user` that prevents GC leaks."""
    task = asyncio.create_task(run_for_user(user_id), name=f"run-for-user:{user_id}")
    _BG_TASKS.add(task)
    task.add_done_callback(_on_bg_task_done)
    return task


def _on_bg_task_done(task: asyncio.Task) -> None:
    _BG_TASKS.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        log.exception("Background run task crashed: %s", exc, exc_info=exc)


async def run_for_user(user_id: UUID) -> None:
    """Load the user + profile, run the update, persist a RunLog, email the user."""
    user_lock = _lock_for(user_id)
    async with user_lock:
        async with _BROWSER_SEMAPHORE:
            await _run_for_user_impl(user_id)


async def _run_for_user_impl(user_id: UUID) -> None:
    async with SessionLocal() as db:
        result = await db.execute(
            select(User, NaukriProfile)
            .join(NaukriProfile, NaukriProfile.user_id == User.id)
            .where(User.id == user_id)
            # Explicitly pull the deferred resume blob; other big fields stay
            # hydrated by default.
            .options(undefer(NaukriProfile.resume_bytes))
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

        # Capture everything off the ORM rows while the session is open — once
        # the `async with` exits we want zero attribute-lazy-loads on detached
        # instances (which would silently fail in async context).
        user_id_local = user.id
        user_email = user.email
        user_name = user.name
        naukri_email = profile.naukri_email
        naukri_password = decrypt_secret(profile.naukri_password_enc)
        resume_bytes = profile.resume_bytes
        # Two different filenames:
        #   - `naukri_upload_name`: what we hand to Playwright → Chromium →
        #     Naukri's multipart upload. Must be `<Name>_DD_Mon_YYYY.pdf` so
        #     recruiters see a freshly dated file every day.
        #   - `email_attachment_name`: the user's original uploaded filename.
        #     The success email is a record of "what was on your system" so
        #     we preserve whatever they picked.
        naukri_upload_name = build_resume_filename(user_name, date.today())
        email_attachment_name = profile.resume_filename or naukri_upload_name
        initial_state_json = _safe_decrypt_session(profile)
        profile_id = profile.id

    settings = get_settings()

    _purge_legacy_profile_dir(user_id_local)

    cfg = RunConfig(
        naukri_email=naukri_email,
        naukri_password=naukri_password,
        resume_bytes=resume_bytes,
        resume_filename=naukri_upload_name,
        initial_storage_state_json=initial_state_json,
        headed=settings.playwright_headed,
        max_retries=2,
    )

    log.info("Starting run for user=%s", user_email)
    started_at = _utcnow()
    try:
        result = await run_naukri_update(cfg)
    except Exception as e:  # noqa: BLE001
        log.exception("Unhandled error in runner")
        result = None
        error = str(e)
    else:
        error = result.error if not result.success else None

    async with SessionLocal() as db:
        refreshed = await db.get(NaukriProfile, profile_id)
        if refreshed:
            refreshed.last_run_at = _utcnow()
            refreshed.last_status = "success" if (result and result.success) else "failed"
            refreshed.last_error = None if (result and result.success) else (error or "unknown")
            # Persist the fresh session so the next run can skip credential login.
            # `final_storage_state_json` is set whenever we successfully logged in,
            # even on partial failures further downstream.
            if result and result.final_storage_state_json:
                try:
                    refreshed.naukri_session_enc = encrypt_secret(
                        result.final_storage_state_json
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning("Failed to encrypt session state for %s: %s", user_email, e)
            elif result and not result.success and _looks_like_session_error(error):
                # Stored session clearly didn't work — clear it so we retry
                # with credentials next time instead of looping on a bad state.
                refreshed.naukri_session_enc = None

        log_row = RunLog(
            user_id=user_id_local,
            started_at=started_at,
            finished_at=_utcnow(),
            status="success" if (result and result.success) else "failed",
            attempts=result.attempts if result else 0,
            error=None if (result and result.success) else (error or "unknown"),
        )
        db.add(log_row)
        await db.commit()

    today = datetime.now().strftime("%d-%b-%Y")
    if result and result.success:
        await send_email_async(
            to_email=user_email,
            subject=f"Resume & Profile Updated - {today}",
            body=(
                f"Hi {user_name},\n\n"
                f"Your Naukri profile was updated successfully on {today}.\n\n"
                f"— Naukri Auto Update"
            ),
            attachment_bytes=resume_bytes,
            attachment_name=email_attachment_name,
        )
    else:
        await send_email_async(
            to_email=user_email,
            subject=f"Naukri Update Failed - {today}",
            body=(
                f"Hi {user_name},\n\n"
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


def _safe_decrypt_session(profile: NaukriProfile) -> str | None:
    """Decrypt the stored session blob, or return None + wipe if it's corrupt."""
    if not profile.naukri_session_enc:
        return None
    try:
        return decrypt_secret(profile.naukri_session_enc)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "Could not decrypt stored Naukri session for user_id=%s (%s) — "
            "will log in fresh.",
            profile.user_id,
            e,
        )
        # Clear it so we don't keep hitting the same failure on every run.
        profile.naukri_session_enc = None
        return None


def _looks_like_session_error(error: str | None) -> bool:
    """Heuristic: was the failure caused by an invalid/missing Naukri session?

    Kept narrow — we only wipe the stored session on clear login-page-related
    signals (URLs, input IDs specific to Naukri's login DOM, OTP/captcha).
    The bare word "login" is too broad: it appears in many healthy log lines
    ("Login successful"), so we avoid matching on it alone.
    """
    if not error:
        return False
    lowered = error.lower()
    return any(
        needle in lowered
        for needle in (
            "nlogin",
            "/login",
            "usernamefield",
            "passwordfield",
            "emailtxt",
            "#pwd1",
            "#sbtlog",
            "captcha",
            "otp",
            "unauthorized",
        )
    )


def _purge_legacy_profile_dir(user_id: UUID) -> None:
    """Remove the old per-user persistent Chromium profile dir if it still exists."""
    legacy = os.path.join(_LEGACY_PW_PROFILE_ROOT, str(user_id))
    if os.path.isdir(legacy):
        try:
            shutil.rmtree(legacy)
            log.info("Removed legacy on-disk Playwright profile at %s", legacy)
        except OSError as e:
            log.info("Could not remove legacy profile at %s: %s", legacy, e)


async def _record_failure(db, user, profile, reason: str) -> None:
    now = _utcnow()
    profile.last_run_at = now
    profile.last_status = "skipped"
    profile.last_error = reason
    db.add(
        RunLog(
            user_id=user.id,
            started_at=now,
            finished_at=now,
            status="skipped",
            attempts=0,
            error=reason,
        )
    )
    await db.commit()
