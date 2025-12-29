from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LeaseStatus


class LeaseCreate(BaseModel):
    owner_id: Optional[int] = Field(default=None, description="Owner id (agent/admin only)")
    property_id: int
    tenant_user_id: Optional[int] = None
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None

    status: LeaseStatus = LeaseStatus.draft
    start_date: date
    end_date: date

    monthly_rent: float
    security_deposit: float

    late_fee_amount: Optional[float] = None
    late_fee_percentage: Optional[float] = None
    grace_period_days: int = 5
    payment_due_day: int = 1

    lease_terms: Optional[Dict[str, Any]] = None
    special_clauses: Optional[str] = None
    lease_document_id: Optional[int] = None


class Lease(BaseModel):
    id: int
    property_id: int
    owner_id: int
    tenant_user_id: Optional[int] = None
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None
    status: LeaseStatus
    start_date: date
    end_date: date
    monthly_rent: float
    security_deposit: float
    late_fee_amount: Optional[float] = None
    late_fee_percentage: Optional[float] = None
    grace_period_days: int
    payment_due_day: int
    lease_terms: Optional[Dict[str, Any]] = None
    special_clauses: Optional[str] = None
    signed_by_tenant_at: Optional[datetime] = None
    signed_by_owner_at: Optional[datetime] = None
    lease_document_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LeaseUploadSigned(BaseModel):
    lease_document_id: int
    signed_by_owner: bool = True
    signed_by_tenant: bool = False


class LeaseRenew(BaseModel):
    start_date: date
    end_date: date
    monthly_rent: Optional[float] = None
    security_deposit: Optional[float] = None
    make_active: bool = False

