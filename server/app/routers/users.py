"""User / profile / schedule / resume endpoints."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app import security
from app.db import get_db
from app.deps import get_current_user
from app.models import NaukriProfile, RunLog, User
from app.runner_service import spawn_run_for_user
from app.scheduler import schedule_user_jobs
from app.schemas import (
    MeOut,
    MessageOut,
    ProfileOut,
    RunLogOut,
    UserOut,
    UserUpdateIn,
)

router = APIRouter(prefix="/api/me", tags=["me"])

MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB


# ------------------------------ ME ----------------------------------------

@router.get("", response_model=MeOut)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    profile = await _get_or_none_profile(db, user.id)
    return MeOut(
        user=UserOut.model_validate(user),
        profile=ProfileOut.model_validate(profile) if profile else None,
    )


@router.patch("", response_model=UserOut)
async def update_me(
    payload: UserUpdateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if payload.name is not None:
        user.name = payload.name

    if payload.new_password:
        if not payload.current_password or not security.verify_password(
            payload.current_password, user.password_hash
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
            )
        user.password_hash = security.hash_password(payload.new_password)

    await db.commit()
    await db.refresh(user)
    return user


# --------------------------- PROFILE / SCHEDULE ---------------------------

@router.put("/profile", response_model=ProfileOut)
async def upsert_profile(
    naukri_email: Optional[str] = Form(default=None),
    naukri_password: Optional[str] = Form(default=None),
    schedule_mode: Optional[str] = Form(default=None),
    schedule_time1: Optional[str] = Form(default=None),
    schedule_time2: Optional[str] = Form(default=None),
    enabled: Optional[bool] = Form(default=None),
    resume: Optional[UploadFile] = File(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NaukriProfile:
    """
    Single endpoint to update any subset of fields (incl. optional resume upload).
    Sent as multipart/form-data so the file can be included on the same request.
    """
    profile = await _get_or_none_profile(db, user.id)
    created = False
    if not profile:
        profile = NaukriProfile(
            user_id=user.id,
            schedule_mode="once",
            schedule_time1=time(9, 30),
            enabled=True,
        )
        db.add(profile)
        created = True

    if naukri_email is not None and naukri_email != "":
        # Switching to a different Naukri account invalidates the stored
        # browser session — it belongs to the old login.
        if profile.naukri_email and profile.naukri_email != naukri_email:
            profile.naukri_session_enc = None
        profile.naukri_email = naukri_email

    if naukri_password:
        profile.naukri_password_enc = security.encrypt_secret(naukri_password)
        # A password change almost certainly invalidates any cached cookies.
        profile.naukri_session_enc = None

    if schedule_mode in ("once", "twice"):
        profile.schedule_mode = schedule_mode

    if schedule_time1:
        profile.schedule_time1 = _parse_time(schedule_time1)
    if schedule_time2:
        profile.schedule_time2 = _parse_time(schedule_time2)
    if profile.schedule_mode == "once":
        profile.schedule_time2 = None

    if enabled is not None:
        profile.enabled = enabled

    if resume is not None and resume.filename:
        if not resume.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported"
            )
        # Starlette exposes `UploadFile.size` when the client set Content-Length,
        # which is almost always the case for multipart PDF uploads. Reject
        # oversize bodies BEFORE pulling the whole payload into memory — the
        # prior version called `.read()` first and a malicious client could
        # OOM the process by streaming gigabytes before we checked.
        if resume.size is not None and resume.size > MAX_RESUME_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Resume must be <= 5 MB",
            )
        data = await resume.read()
        # Defensive re-check in case `size` was not advertised.
        if len(data) > MAX_RESUME_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Resume must be <= 5 MB",
            )
        profile.resume_bytes = data
        # Keep the user's original filename so the UI, preview and download
        # show exactly what they uploaded. The Naukri-facing rename happens
        # at run time in runner_service (see `build_resume_filename`).
        profile.resume_filename = resume.filename
        profile.resume_uploaded_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(profile)

    schedule_user_jobs(profile)
    _ = created
    return profile


@router.delete("/naukri-session", response_model=MessageOut)
async def reset_naukri_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    """Forget the cached Naukri browser session — next run will log in fresh."""
    profile = await _get_or_none_profile(db, user.id)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No Naukri profile yet")
    if profile.naukri_session_enc is None:
        return MessageOut(detail="No cached session to reset")
    profile.naukri_session_enc = None
    await db.commit()
    return MessageOut(detail="Cached Naukri session cleared")


@router.get("/resume")
async def download_resume(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # The resume blob is deferred on the model; explicitly undefer so we fetch
    # the PDF in the same round-trip instead of triggering a second SELECT.
    result = await db.execute(
        select(NaukriProfile)
        .where(NaukriProfile.user_id == user.id)
        .options(undefer(NaukriProfile.resume_bytes))
    )
    profile = result.scalar_one_or_none()
    if not profile or not profile.resume_bytes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No resume uploaded")
    return Response(
        content=profile.resume_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{profile.resume_filename or "resume.pdf"}"'
        },
    )


# ------------------------------- RUNS -------------------------------------

@router.get("/runs", response_model=list[RunLogOut])
async def list_runs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RunLog]:
    result = await db.execute(
        select(RunLog).where(RunLog.user_id == user.id).order_by(RunLog.started_at.desc()).limit(20)
    )
    return list(result.scalars().all())


@router.post("/run-now", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
async def run_now(user: User = Depends(get_current_user)) -> MessageOut:
    spawn_run_for_user(user.id)
    return MessageOut(detail="Run started. You'll get an email when it finishes.")


# ------------------------------ helpers -----------------------------------

async def _get_or_none_profile(db: AsyncSession, user_id) -> NaukriProfile | None:
    result = await db.execute(select(NaukriProfile).where(NaukriProfile.user_id == user_id))
    return result.scalar_one_or_none()


def _parse_time(raw: str) -> time:
    """Accept 'HH:MM' or 'HH:MM:SS'."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid time: {raw}")
