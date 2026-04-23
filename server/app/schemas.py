"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------- auth ----------------

class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


# ---------------- user ----------------

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    name: str
    subscription: str
    role: str = "user"
    subscribed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class UserUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=200)

    @field_validator("new_password")
    @classmethod
    def _require_current(cls, v, info):
        if v and not info.data.get("current_password"):
            raise ValueError("current_password is required to change password")
        return v


# ---------------- naukri profile ----------------

class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    naukri_email: Optional[EmailStr] = None
    resume_filename: Optional[str] = None
    resume_uploaded_at: Optional[datetime] = None
    schedule_mode: Literal["once", "twice"] = "once"
    schedule_time1: time
    schedule_time2: Optional[time] = None
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None


class ProfileUpdateIn(BaseModel):
    naukri_email: Optional[EmailStr] = None
    naukri_password: Optional[str] = Field(default=None, min_length=1, max_length=200)
    schedule_mode: Optional[Literal["once", "twice"]] = None
    schedule_time1: Optional[time] = None
    schedule_time2: Optional[time] = None
    enabled: Optional[bool] = None


class RunLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    attempts: int
    error: Optional[str] = None


class MeOut(BaseModel):
    user: UserOut
    profile: Optional[ProfileOut] = None


class MessageOut(BaseModel):
    detail: str


# ---------------- billing ----------------

class BillingPlan(BaseModel):
    id: Literal["free", "paid"]
    name: str
    price_inr: int
    features: list[str]


class BillingOut(BaseModel):
    subscription: str
    subscribed_at: Optional[datetime] = None
    plans: list[BillingPlan]


# ---------------- admin ----------------

class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    name: str
    role: str
    subscription: str
    subscribed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    has_profile: bool = False
    profile_enabled: Optional[bool] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    run_count: int = 0


class AdminUserUpdateIn(BaseModel):
    subscription: Optional[Literal["free", "paid"]] = None
    role: Optional[Literal["user", "admin"]] = None
    profile_enabled: Optional[bool] = None


class AdminRunLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    user_email: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    attempts: int
    error: Optional[str] = None


class AdminStatsOut(BaseModel):
    total_users: int
    paid_users: int
    total_profiles: int
    enabled_profiles: int
    runs_24h: int
    failures_24h: int
