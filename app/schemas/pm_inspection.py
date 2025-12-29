from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InspectionType


class InspectionChecklistCreate(BaseModel):
    owner_id: Optional[int] = Field(default=None, description="Owner id (agent/admin only)")
    lease_id: int
    inspection_type: InspectionType
    rooms_data: Optional[Dict[str, Any]] = None
    overall_notes: Optional[str] = None
    conducted_at: Optional[datetime] = None


class InspectionChecklist(BaseModel):
    id: int
    property_id: int
    lease_id: int
    owner_id: int
    inspection_type: InspectionType
    conducted_by_user_id: int
    conducted_at: datetime
    rooms_data: Optional[Dict[str, Any]] = None
    overall_notes: Optional[str] = None
    tenant_signature_document_id: Optional[int] = None
    owner_signature_document_id: Optional[int] = None
    signed_by_tenant_at: Optional[datetime] = None
    signed_by_owner_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InspectionSign(BaseModel):
    tenant_signature_document_id: Optional[int] = None
    owner_signature_document_id: Optional[int] = None

