"""Billing / subscription endpoints (mock implementation)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import BillingOut, BillingPlan, MessageOut, UserOut

router = APIRouter(prefix="/api/me/billing", tags=["billing"])


PLANS: list[BillingPlan] = [
    BillingPlan(
        id="free",
        name="Free",
        price_inr=0,
        features=[
            "1 scheduled update per day",
            "Resume upload up to 5 MB",
            "Email notifications",
        ],
    ),
    BillingPlan(
        id="paid",
        name="Pro",
        price_inr=299,
        features=[
            "Twice-daily scheduled updates",
            "Run now (on-demand) without limits",
            "Priority support",
            "Early access to new features",
        ],
    ),
]


@router.get("", response_model=BillingOut)
async def get_billing(user: User = Depends(get_current_user)) -> BillingOut:
    return BillingOut(
        subscription=user.subscription,
        subscribed_at=user.subscribed_at,
        plans=PLANS,
    )


@router.post("/subscribe", response_model=UserOut)
async def subscribe(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Mock checkout - flips the user to paid. Wire to Stripe/Razorpay later."""
    if user.subscription == "paid":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Already on Pro plan")
    user.subscription = "paid"
    user.subscribed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/cancel", response_model=UserOut)
async def cancel(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if user.subscription != "paid":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Not on Pro plan")
    user.subscription = "free"
    user.subscribed_at = None
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/plans", response_model=list[BillingPlan])
async def list_plans() -> list[BillingPlan]:
    return PLANS
