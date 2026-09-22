from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_in: UserCreate,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Реєстрація нового користувача."""
    user_service = UserService(session)
    return await user_service.register_user(user_in)


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Вхід у систему (отримання JWT-токена)."""
    user_service = UserService(session)
    # OAuth2PasswordRequestForm використовує поле .username для логіна/email
    return await user_service.authenticate_user(
        email=form_data.username, password=form_data.password
    )
