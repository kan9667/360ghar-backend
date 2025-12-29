from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import Agent as AgentSchema


class OwnerRMAssignmentUpdate(BaseModel):
    agent_id: Optional[int] = Field(default=None, description="Agent id to assign; null to unassign")


class OwnerRMAssignmentCreate(BaseModel):
    owner_user_id: Optional[int] = Field(
        default=None,
        description="Owner user id (required for admin; ignored for owner role)",
    )
    agent_id: Optional[int] = Field(default=None, description="Agent id to assign; null to unassign")


class OwnerRMAssignmentResponse(BaseModel):
    owner_user_id: int
    agent_id: Optional[int] = None
    agent: Optional[AgentSchema] = None

    model_config = ConfigDict(from_attributes=True)
