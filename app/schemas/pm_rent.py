from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RentChargeStatus


class RentChargeGenerateRequest(BaseModel):
    owner_id: Optional[int] = Field(default=None, description="Owner id (agent/admin only)")
    lease_id: Optional[int] = None
    start_month: Optional[date] = None
    months: int = Field(default=1, ge=1, le=24)


class RentCharge(BaseModel):
    id: int
    lease_id: int
    property_id: int
    owner_id: int
    tenant_user_id: Optional[int] = None
    billing_month: date
    period_start: date
    period_end: date
    due_date: date
    amount_due: float
    late_fee_assessed: float
    status: RentChargeStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RentChargeWithTotals(BaseModel):
    charge: RentCharge
    amount_paid_total: float
    amount_due_total: float
    outstanding: float


class RentPaymentCreate(BaseModel):
    charge_id: int
    amount_paid: float = Field(gt=0)
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    receipt_document_id: Optional[int] = None


class RentPayment(BaseModel):
    id: int
    charge_id: int
    lease_id: int
    property_id: int
    owner_id: int
    tenant_user_id: Optional[int] = None
    paid_at: datetime
    amount_paid: float
    payment_method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    receipt_document_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

