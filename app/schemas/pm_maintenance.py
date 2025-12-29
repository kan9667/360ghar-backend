from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    MaintenanceCategory,
    MaintenanceRequestStatus,
    MaintenanceUrgency,
    WorkOrderStatus,
)


class MaintenanceRequestCreate(BaseModel):
    property_id: int
    category: MaintenanceCategory
    urgency: MaintenanceUrgency
    title: str
    description: Optional[str] = None
    preferred_contact_method: Optional[str] = None
    availability_notes: Optional[str] = None


class MaintenanceRequestUpdate(BaseModel):
    request_status: Optional[MaintenanceRequestStatus] = None
    assigned_agent_id: Optional[int] = None
    work_order_status: Optional[WorkOrderStatus] = None
    priority: Optional[str] = None
    estimated_cost: Optional[float] = Field(default=None, ge=0)
    actual_cost: Optional[float] = Field(default=None, ge=0)
    scheduled_for: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None


class MaintenanceRequest(BaseModel):
    id: int
    property_id: int
    lease_id: Optional[int] = None
    owner_id: int
    tenant_user_id: Optional[int] = None
    category: MaintenanceCategory
    urgency: MaintenanceUrgency
    title: str
    description: Optional[str] = None
    preferred_contact_method: Optional[str] = None
    availability_notes: Optional[str] = None
    request_status: MaintenanceRequestStatus
    assigned_agent_id: Optional[int] = None
    work_order_status: Optional[WorkOrderStatus] = None
    priority: Optional[str] = None
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    scheduled_for: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

