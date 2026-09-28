from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# Base schema with shared attributes
class UserBase(BaseModel):
    email: EmailStr


# Schema for user registration
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def check_password_length(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        return v


# Response schema sent back to client (never exposes password)
class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
