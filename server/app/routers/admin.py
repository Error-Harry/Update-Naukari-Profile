"""Admin endpoints - list/manage users, view all runs, basic stats."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.deps import require_admin
from app.models import NaukriProfile, RunLog, User
from app.scheduler import schedule_user_jobs
from app.schemas import (
    AdminRunLogOut,
    AdminStatsOut,
    AdminUserOut,
    AdminUserUpdateIn,
    MessageOut,
)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# --------------------------------- USERS ----------------------------------

@router.get("/users", response_model=list[AdminUserOut])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[AdminUserOut]:
    users_res = await db.execute(
        select(User).options(selectinload(User.profile)).order_by(User.created_at.desc())
    )
    users = list(users_res.scalars().all())

    counts_res = await db.execute(
        select(RunLog.user_id, func.count(RunLog.id)).group_by(RunLog.user_id)
    )
    counts = {row[0]: row[1] for row in counts_res.all()}

    out: list[AdminUserOut] = []
    for u in users:
        profile = u.profile
        out.append(
            AdminUserOut(
                id=u.id,
                email=u.email,
                name=u.name,
                role=u.role,
                subscription=u.subscription,
                subscribed_at=u.subscribed_at,
                created_at=u.created_at,
                has_profile=profile is not None,
                profile_enabled=profile.enabled if profile else None,
                last_run_at=profile.last_run_at if profile else None,
                last_status=profile.last_status if profile else None,
                run_count=int(counts.get(u.id, 0)),
            )
        )
    return out


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdateIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AdminUserOut:
    res = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user_id)
    )
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.subscription is not None and payload.subscription != user.subscription:
        user.subscription = payload.subscription
        user.subscribed_at = datetime.utcnow() if payload.subscription == "paid" else None

    if payload.role is not None:
        if user.id == admin.id and payload.role != "admin":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Cannot demote yourself"
            )
        user.role = payload.role

    if payload.profile_enabled is not None and user.profile:
        user.profile.enabled = payload.profile_enabled

    await db.commit()
    await db.refresh(user)
    if user.profile:
        schedule_user_jobs(user.profile)

    return AdminUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        subscription=user.subscription,
        subscribed_at=user.subscribed_at,
        created_at=user.created_at,
        has_profile=user.profile is not None,
        profile_enabled=user.profile.enabled if user.profile else None,
        last_run_at=user.profile.last_run_at if user.profile else None,
        last_status=user.profile.last_status if user.profile else None,
        run_count=0,
    )


@router.delete("/users/{user_id}", response_model=MessageOut)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> MessageOut:
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.delete(user)
    await db.commit()
    return MessageOut(detail=f"User {user.email} deleted")


# --------------------------------- RUNS -----------------------------------

@router.get("/runs", response_model=list[AdminRunLogOut])
async def list_runs(
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
) -> list[AdminRunLogOut]:
    limit = max(1, min(limit, 500))
    res = await db.execute(
        select(RunLog, User.email)
        .join(User, User.id == RunLog.user_id)
        .order_by(RunLog.started_at.desc())
        .limit(limit)
    )
    out: list[AdminRunLogOut] = []
    for run, email in res.all():
        out.append(
            AdminRunLogOut(
                id=run.id,
                user_id=run.user_id,
                user_email=email,
                started_at=run.started_at,
                finished_at=run.finished_at,
                status=run.status,
                attempts=run.attempts,
                error=run.error,
            )
        )
    return out


# --------------------------------- STATS ----------------------------------

@router.get("/stats", response_model=AdminStatsOut)
async def stats(db: AsyncSession = Depends(get_db)) -> AdminStatsOut:
    total_users = int((await db.execute(select(func.count(User.id)))).scalar_one() or 0)
    paid_users = int(
        (await db.execute(select(func.count(User.id)).where(User.subscription == "paid"))).scalar_one() or 0
    )
    total_profiles = int(
        (await db.execute(select(func.count(NaukriProfile.id)))).scalar_one() or 0
    )
    enabled_profiles = int(
        (await db.execute(select(func.count(NaukriProfile.id)).where(NaukriProfile.enabled.is_(True)))).scalar_one() or 0
    )
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    runs_24h = int(
        (await db.execute(select(func.count(RunLog.id)).where(RunLog.started_at >= since))).scalar_one() or 0
    )
    failures_24h = int(
        (
            await db.execute(
                select(func.count(RunLog.id)).where(
                    RunLog.started_at >= since, RunLog.status != "success"
                )
            )
        ).scalar_one() or 0
    )
    return AdminStatsOut(
        total_users=total_users,
        paid_users=paid_users,
        total_profiles=total_profiles,
        enabled_profiles=enabled_profiles,
        runs_24h=runs_24h,
        failures_24h=failures_24h,
    )
