"""
Auth business logic, kept out of the route handlers (see docs/architecture.md
— "service layer between routes and the database"). Routes only validate the
request and call these functions; everything here is unit-testable without
spinning up the ASGI app.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import EmailAlreadyRegisteredError, InvalidCredentialsError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, payload: RegisterRequest) -> TokenResponse:
    existing = await get_user_by_email(db, payload.email)
    if existing is not None:
        raise EmailAlreadyRegisteredError()

    user = User(
        name=payload.name,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


async def authenticate_user(db: AsyncSession, payload: LoginRequest) -> TokenResponse:
    user = await get_user_by_email(db, payload.email)
    # hashed_password is nullable at the DB level (Phase 1 note in
    # models/user.py), so a user with no password set can never log in —
    # treat that the same as a wrong password rather than a 500.
    if user is None or user.hashed_password is None:
        raise InvalidCredentialsError()
    if not verify_password(payload.password, user.hashed_password):
        raise InvalidCredentialsError()

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))
