from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.user_repo = UserRepository(session)

    async def register_user(self, user_in: UserCreate) -> User:
        """Реєструє нового користувача з перевіркою унікальності email."""
        existing_user = await self.user_repo.get_by_email(user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Користувач із таким email вже зареєстрований.",
            )

        hashed_password = get_password_hash(user_in.password)
        return await self.user_repo.create(
            email=user_in.email, hashed_password=hashed_password
        )

    async def authenticate_user(self, email: str, password: str) -> Token:
        """Перевіряє облікові дані та повертає JWT-токен."""
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неправильний email або пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(subject=user.id)
        return Token(access_token=token)
