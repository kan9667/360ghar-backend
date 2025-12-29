from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from app.schemas.pm_lease import Lease as LeaseSchema


class TenantSummary(BaseModel):
    user_id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    active_leases_count: int = 0


class TenantDetail(BaseModel):
    user_id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    leases: List[LeaseSchema] = []

