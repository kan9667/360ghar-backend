from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.enums import VisitContext, VisitStatus
from app.schemas.property import Property as PropertySchema
from app.schemas.user import User as UserSchema

class VisitBase(BaseModel):
    property_id: int
    scheduled_date: datetime
    special_requirements: Optional[str] = None
    visit_context: VisitContext = VisitContext.property_tour
    counterparty_user_id: Optional[int] = None
    conversation_id: Optional[int] = None
    match_id: Optional[int] = None

class VisitCreate(BaseModel):
    property_id: int
    scheduled_date: datetime
    user_id: Optional[int] = None
    special_requirements: Optional[str] = None
    visit_context: VisitContext = VisitContext.property_tour
    counterparty_user_id: Optional[int] = None
    conversation_id: Optional[int] = None
    match_id: Optional[int] = None

class VisitUpdate(BaseModel):
    scheduled_date: Optional[datetime] = None
    status: Optional[VisitStatus] = None
    special_requirements: Optional[str] = None
    visit_notes: Optional[str] = None
    visitor_feedback: Optional[str] = None
    interest_level: Optional[str] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    visit_context: Optional[VisitContext] = None
    counterparty_user_id: Optional[int] = None
    conversation_id: Optional[int] = None
    match_id: Optional[int] = None

class VisitReschedule(BaseModel):
    new_date: datetime
    reason: Optional[str] = None

class VisitCancel(BaseModel):
    reason: str

class Visit(VisitBase):
    id: int
    user_id: int
    agent_id: Optional[int] = None
    actual_date: Optional[datetime] = None
    status: VisitStatus
    visit_notes: Optional[str] = None
    visitor_feedback: Optional[str] = None
    interest_level: Optional[str] = None
    follow_up_required: bool
    follow_up_date: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    rescheduled_from: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    property: Optional[PropertySchema] = None
    counterparty_user: Optional[UserSchema] = None
    
    model_config = ConfigDict(from_attributes=True)

class VisitList(BaseModel):
    visits: list[Visit]
    total: int
    upcoming: int
    completed: int
    cancelled: int

class VisitSlice(BaseModel):
    visits: list[Visit]
    total: int
