"""
Shared API dependencies.

get_current_user is what makes a route "protected" (spec section 4): add
`current_user: User = Depends(get_current_user)` to any route's signature
and FastAPI will 401 the request before your handler ever runs if the
token is missing, malformed, expired, or points at a deleted user.
"""
import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import NotAuthenticatedError
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise NotAuthenticatedError()

    user_id_str = decode_access_token(credentials.credentials)
    if user_id_str is None:
        raise NotAuthenticatedError()

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise NotAuthenticatedError()

    user = await db.get(User, user_id)
    if user is None:
        raise NotAuthenticatedError()

    return user
