from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RentRollItem(BaseModel):
    property_id: int
    title: str
    occupancy: str
    tenant_user_id: Optional[int] = None
    monthly_rent: Optional[float] = None
    lease_end_date: Optional[date] = None


class IncomeReport(BaseModel):
    total_income: float
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class ExpenseReport(BaseModel):
    total_expenses: float
    start: Optional[date] = None
    end: Optional[date] = None


class PnLReport(BaseModel):
    total_income: float
    total_expenses: float
    net_income: float
    start: Optional[date] = None
    end: Optional[date] = None


class OccupancyReport(BaseModel):
    total: int
    occupied: int
    vacant: int


class MaintenanceReport(BaseModel):
    total_requests: int

