from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DashboardOverview(BaseModel):
    total_properties: int
    occupied_properties: int
    vacant_properties: int
    under_maintenance_properties: int
    monthly_revenue_current: float
    monthly_revenue_previous: float
    outstanding_rent_total: float
    upcoming_expenses_total: float


class ActivityItem(BaseModel):
    type: str
    at: str
    id: Optional[int] = None
    property_id: Optional[int] = None
    lease_id: Optional[int] = None
    amount: Optional[float] = None
    status: Optional[str] = None

