"""Pydantic schemas for the User resource — what we return to clients.

Kept separate from app.models.user.User (the ORM model) on purpose: the
response shape should never accidentally include hashed_password just
because a new column gets added to the table.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    github_username: str | None = None
    target_role: str | None = None
    target_location: str | None = None
    experience_level: str | None = None
    created_at: datetime
