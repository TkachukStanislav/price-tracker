from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Базова схема із загальними полями
class UserBase(BaseModel):
    email: EmailStr


# Схема для реєстрації (вхідні дані: пароль обов'язковий)
class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=100)


# Схема для повернення користувача клієнту (пароль приховано!)
class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    # Дозволяє Pydantic читати дані прямо з об'єктів SQLAlchemy ORM
    model_config = ConfigDict(from_attributes=True)
