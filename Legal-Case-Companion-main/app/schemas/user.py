from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str

    model_config = {"extra": "forbid"}


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    account_status: str
    role: str

    model_config = {"from_attributes": True}
