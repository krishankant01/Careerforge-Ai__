"""
Password hashing and JWT helpers.

Passwords are hashed with bcrypt via passlib — plaintext passwords are never
stored, logged, or returned in any response (see spec section 28: never
store plain-text passwords).

JWTs are signed with HS256 using JWT_SECRET. The token's only payload is the
user's id (`sub` claim) and an expiry (`exp`); we deliberately keep it thin
so a token never goes stale relative to the user's row — every request that
needs user data (email, role, etc.) fetches the current row instead of
trusting a value baked into the token.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns the user_id string from the token's `sub` claim, or None if the
    token is missing, malformed, expired, or signed with a different secret."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
