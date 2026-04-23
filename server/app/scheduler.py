"""APScheduler wiring — one cron job per schedule slot, per user."""

from __future__ import annotations

import logging
from datetime import time
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import NaukriProfile
from app.runner_service import run_for_user

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _job_id(user_id: UUID, slot: int) -> str:
    return f"user:{user_id}:slot:{slot}"


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = AsyncIOScheduler(timezone=settings.tz)
    return _scheduler


async def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        log.info("APScheduler started (tz=%s)", sched.timezone)
    await reload_all_jobs()


async def shutdown_scheduler() -> None:
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
        log.info("APScheduler stopped")


async def reload_all_jobs() -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(NaukriProfile))
        profiles = list(result.scalars().all())
    sched = get_scheduler()
    for job in list(sched.get_jobs()):
        sched.remove_job(job.id)
    for p in profiles:
        schedule_user_jobs(p)
    log.info("Reloaded %d user schedules", len(profiles))


def schedule_user_jobs(profile: NaukriProfile) -> None:
    """(Re)create both slot-1 and slot-2 jobs for a user based on current settings."""
    sched = get_scheduler()
    user_id = profile.user_id

    _remove_if_exists(sched, _job_id(user_id, 1))
    _remove_if_exists(sched, _job_id(user_id, 2))

    if not profile.enabled:
        return

    _add_cron(sched, _job_id(user_id, 1), profile.schedule_time1, user_id)
    if profile.schedule_mode == "twice" and profile.schedule_time2:
        _add_cron(sched, _job_id(user_id, 2), profile.schedule_time2, user_id)


def _remove_if_exists(sched: AsyncIOScheduler, job_id: str) -> None:
    if sched.get_job(job_id):
        sched.remove_job(job_id)


def _add_cron(sched: AsyncIOScheduler, job_id: str, at: time, user_id: UUID) -> None:
    trigger = CronTrigger(hour=at.hour, minute=at.minute, timezone=sched.timezone)
    sched.add_job(
        run_for_user,
        trigger=trigger,
        id=job_id,
        args=[user_id],
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 30,
        replace_existing=True,
    )
    log.info("Scheduled %s at %02d:%02d", job_id, at.hour, at.minute)
