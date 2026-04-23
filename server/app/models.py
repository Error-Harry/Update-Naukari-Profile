"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    subscription: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    subscribed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped[Optional["NaukriProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    run_logs: Mapped[list["RunLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class NaukriProfile(Base):
    __tablename__ = "naukri_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    naukri_email: Mapped[Optional[str]] = mapped_column(String(320))
    naukri_password_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)

    resume_filename: Mapped[Optional[str]] = mapped_column(String(300))
    resume_bytes: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    resume_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    schedule_mode: Mapped[str] = mapped_column(String(10), default="once", nullable=False)
    schedule_time1: Mapped[time] = mapped_column(Time(timezone=False), default=time(9, 30), nullable=False)
    schedule_time2: Mapped[Optional[time]] = mapped_column(Time(timezone=False))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[Optional[str]] = mapped_column(String(20))
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="run_logs")
