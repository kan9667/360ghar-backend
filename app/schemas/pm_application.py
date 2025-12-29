from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TenantStatus


class RentalApplicationFormCreate(BaseModel):
    owner_id: Optional[int] = Field(default=None, description="Owner id (agent/admin only)")
    property_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    application_fee_amount: Optional[float] = None
    required_document_types: Optional[Dict[str, Any]] = None
    questions: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None


class RentalApplicationForm(BaseModel):
    id: int
    owner_id: int
    property_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    slug: str
    is_active: bool
    application_fee_amount: Optional[float] = None
    required_document_types: Optional[Dict[str, Any]] = None
    questions: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PublicRentalApplicationForm(BaseModel):
    slug: str
    title: str
    description: Optional[str] = None
    property_id: Optional[int] = None
    application_fee_amount: Optional[float] = None
    required_document_types: Optional[Dict[str, Any]] = None
    questions: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class RentalApplicationSubmit(BaseModel):
    property_id: Optional[int] = None
    applicant_full_name: Optional[str] = None
    applicant_phone: Optional[str] = None
    applicant_email: Optional[str] = None
    answers: Optional[Dict[str, Any]] = None
    application_data: Optional[Dict[str, Any]] = None
    emergency_contacts: Optional[Dict[str, Any]] = None


class RentalApplicationDecision(BaseModel):
    decision: TenantStatus


class RentalApplication(BaseModel):
    id: int
    form_id: int
    property_id: int
    owner_id: int
    status: TenantStatus
    applicant_user_id: Optional[int] = None
    applicant_full_name: Optional[str] = None
    applicant_phone: Optional[str] = None
    applicant_email: Optional[str] = None
    answers: Optional[Dict[str, Any]] = None
    application_data: Optional[Dict[str, Any]] = None
    emergency_contacts: Optional[Dict[str, Any]] = None
    submitted_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None
    decided_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

