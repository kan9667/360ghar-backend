"""Auction alert endpoints."""


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1.dependencies.auth import get_current_active_user
from app.core.database import get_db
from app.models.data_hub import AuctionAlert
from app.schemas.data_hub import (
    AuctionAlertCreate,
    AuctionAlertResponse,
    AuctionAlertUpdate,
)
from app.schemas.user import User as UserSchema

router = APIRouter()


@router.get("/auctions/alerts/me", response_model=list[AuctionAlertResponse])
async def get_my_auction_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Get the authenticated user's auction alerts."""
    result = await db.execute(
        select(AuctionAlert).where(AuctionAlert.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/auctions/alerts", response_model=AuctionAlertResponse, status_code=201)
async def create_auction_alert(
    payload: AuctionAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Create a new auction alert for the authenticated user."""
    alert = AuctionAlert(
        user_id=current_user.id,
        bank_name=payload.bank_name,
        property_type=payload.property_type,
        min_price=payload.min_price,
        max_price=payload.max_price,
        alert_channels=payload.alert_channels or ["email"],
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.put("/auctions/alerts/{alert_id}", response_model=AuctionAlertResponse)
async def update_auction_alert(
    alert_id: int,
    payload: AuctionAlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Update an auction alert owned by the authenticated user."""
    result = await db.execute(
        select(AuctionAlert).where(
            AuctionAlert.id == alert_id,
            AuctionAlert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Auction alert not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/auctions/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auction_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Delete an auction alert owned by the authenticated user."""
    result = await db.execute(
        select(AuctionAlert).where(
            AuctionAlert.id == alert_id,
            AuctionAlert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Auction alert not found")
    await db.delete(alert)
    await db.commit()
