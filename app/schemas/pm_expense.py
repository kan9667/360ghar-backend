from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExpenseCategory


class ExpenseCreate(BaseModel):
    owner_id: Optional[int] = Field(default=None, description="Owner id (agent/admin only)")
    property_id: int
    category: ExpenseCategory
    amount: float = Field(gt=0)
    expense_date: date
    description: Optional[str] = None
    notes: Optional[str] = None
    receipt_document_id: Optional[int] = None
    is_recurring: bool = False
    recurrence_rule: Optional[Dict[str, Any]] = None
    next_due_date: Optional[date] = None


class ExpenseUpdate(BaseModel):
    property_id: Optional[int] = None
    category: Optional[ExpenseCategory] = None
    amount: Optional[float] = Field(default=None, gt=0)
    expense_date: Optional[date] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    receipt_document_id: Optional[int] = None
    is_recurring: Optional[bool] = None
    recurrence_rule: Optional[Dict[str, Any]] = None
    next_due_date: Optional[date] = None


class Expense(BaseModel):
    id: int
    property_id: int
    owner_id: int
    category: ExpenseCategory
    amount: float
    expense_date: date
    description: Optional[str] = None
    notes: Optional[str] = None
    receipt_document_id: Optional[int] = None
    is_recurring: bool
    recurrence_rule: Optional[Dict[str, Any]] = None
    next_due_date: Optional[date] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
