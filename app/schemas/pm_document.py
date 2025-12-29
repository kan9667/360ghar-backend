from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentType


class DocumentCreate(BaseModel):
    owner_id: Optional[int] = Field(default=None, description="Owner id (agent/admin only)")
    document_type: DocumentType
    title: str
    user_id: Optional[int] = None
    property_id: Optional[int] = None
    lease_id: Optional[int] = None
    maintenance_request_id: Optional[int] = None
    rental_application_id: Optional[int] = None
    shared_with_tenant: bool = False
    shared_with_agent: bool = False


class Document(BaseModel):
    id: int
    owner_id: int
    user_id: Optional[int] = None
    property_id: Optional[int] = None
    lease_id: Optional[int] = None
    maintenance_request_id: Optional[int] = None
    rental_application_id: Optional[int] = None
    document_type: DocumentType
    title: str
    file_url: str
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    shared_with_tenant: bool
    shared_with_agent: bool
    version: int
    replaces_document_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    shared_with_tenant: Optional[bool] = None
    shared_with_agent: Optional[bool] = None


class DocumentDownload(BaseModel):
    url: str

