from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str
    organization_id: UUID | None = None
    is_active: bool
    created_at: datetime


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
